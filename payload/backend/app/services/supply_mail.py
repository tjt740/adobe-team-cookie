"""supply.ink 的只读取信接口，按完整邮箱查 require，再以其 id 调 getMail。"""
from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
import re
import time
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import select

from app.models.setting import Setting

API_BASE = "https://api.supply.ink/supply"
TOKEN_KEY = "supply_mail_token"


class SupplyMailError(RuntimeError):
    pass


class SupplyAccountNotFound(SupplyMailError):
    pass


def get_token(db) -> str:
    return db.scalar(select(Setting.value).where(Setting.key == TOKEN_KEY)) or ""


def text_from_html(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"<!--[\s\S]*?-->", " ", text)
    text = re.sub(r"<(script|style|head|title|noscript|template|svg|iframe)\b[^>]*>[\s\S]*?</\1\s*>", " ", text, flags=re.I)
    text = re.sub(r"<(script|style|head)\b[^>]*>[\s\S]*$", " ", text, flags=re.I)
    text = re.sub(r"</?(?:br|hr|p|div|tr|td|li|h[1-6])\b[^>]*>", "\n", text, flags=re.I)
    return unescape(re.sub(r"<[^>]*>", " ", text)).strip()


def mail_timestamp(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).replace(".", "", 1).isdigit():
            ts = float(value)
            return ts / 1000 if ts > 10_000_000_000 else ts
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        # supply 的无时区 createTime 按中国标准时间解释，不依赖服务器时区。
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        return dt.timestamp()
    except (ValueError, OverflowError):
        return None


class SupplyMailbox:
    def __init__(self, token: str, *, http=None):
        self.token = re.sub(r"^Bearer\s+", "", token.strip(), flags=re.I)
        self.http = http or requests.Session()
        self.account_ids: dict[str, object] = {}
        self.deadline = None

    def close(self):
        self.http.close()

    def _post(self, path: str, body: dict) -> dict:
        if not self.token:
            raise SupplyMailError("需要邮箱验证码，请先在外部子号的邮件配置中保存 supply.ink Token")
        timeout = min(12, self.deadline - time.monotonic()) if self.deadline is not None else 12
        if timeout <= 0:
            raise SupplyMailError("supply.ink 邮箱匹配超时，请稍后重试")
        try:
            response = self.http.post(API_BASE + path, json=body,
                                      headers={"Token": self.token, "Accept": "application/json"},
                                      timeout=timeout, allow_redirects=False)
        except requests.RequestException:
            raise SupplyMailError("supply.ink 邮件接口连接失败，请稍后重试") from None
        if response.status_code in (401, 403):
            raise SupplyMailError("supply.ink Token 已失效或无取信权限，请重新保存")
        if response.status_code != 200:
            raise SupplyMailError(f"supply.ink 邮件接口返回 HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError:
            raise SupplyMailError("supply.ink 邮件接口返回了无法识别的数据") from None
        if not isinstance(data, dict):
            raise SupplyMailError("supply.ink 邮件接口返回了无法识别的数据")
        if data.get("code") in (401, 403):
            raise SupplyMailError("supply.ink Token 已失效或无取信权限，请重新保存")
        if data.get("code") != 200 and not (path == "/getMail" and data.get("code") == 1005):
            # 不返回第三方错误原文，避免服务端回显连接凭据。
            raise SupplyMailError(f"supply.ink 邮件接口查询失败（code={data.get('code') if isinstance(data.get('code'), int) else 'unknown'}）")
        return data

    def test(self) -> dict:
        data = self._post("/require", {"page": 1, "limit": 1}).get("data") or {}
        return {"ok": True, "total": data.get("total", 0), "message": "supply.ink 邮件连接成功"}

    def _account_id(self, email: str):
        key = email.strip().lower()
        if key in self.account_ids:
            return self.account_ids[key]

        def find(data):
            if not isinstance(data, dict):
                raise SupplyMailError("supply.ink 账号列表格式无效")
            rows = data.get("list") or data.get("rows") or []
            if not isinstance(rows, list):
                raise SupplyMailError("supply.ink 账号列表格式无效")
            for row in rows:
                if isinstance(row, dict) and str(row.get("username") or row.get("email") or row.get("account") or "").strip().lower() == key and row.get("id") is not None:
                    self.account_ids[key] = row["id"]
                    return row["id"], rows
            return None, rows

        data = self._post("/require", {"page": 1, "limit": 50, "username": key}).get("data") or {}
        found, _ = find(data)
        if found is not None:
            return found
        # 与用户脚本一致，不带 status 过滤，只扫描 require 的 id。
        complete = False
        for page in range(1, 6):
            data = self._post("/require", {"page": page, "limit": 200}).get("data") or {}
            found, rows = find(data)
            if found is not None:
                return found
            total = data.get("total")
            if len(rows) < 200 or (isinstance(total, (int, float)) and page * 200 >= total):
                complete = True
                break
        if not complete:
            raise SupplyMailError("supply.ink 账号库查询尚未完成，请稍后重试")
        raise SupplyAccountNotFound("该邮箱不在 supply.ink 可取信账号库中，请检查 Token 所属账号或提供原取信配置")

    def messages(self, email: str, *, limit: int = 5) -> list[dict]:
        payload = self._post("/getMail", {"id": self._account_id(email)})
        if payload.get("code") == 1005:
            return []
        data = payload.get("data")
        rows = (data.get("list") or data.get("rows") or []) if isinstance(data, dict) else data or []
        if not isinstance(rows, list):
            raise SupplyMailError("supply.ink 邮件列表格式无效")
        result = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            recipient = str(row.get("to") or row.get("recipient") or row.get("email") or "").strip()
            addresses = re.findall(r"[\w.+%\-]+@[\w.\-]+", recipient.lower())
            if recipient and email.lower() not in addresses:
                continue
            ts = mail_timestamp(row.get("createTime") or row.get("createdAt") or row.get("sendTime") or row.get("date") or row.get("time"))
            result.append({"id": str(row.get("id", "")),
                           "subject": text_from_html(row.get("subject") or row.get("title")),
                           "body": text_from_html(row.get("content") or row.get("body") or row.get("text")),
                           "sender": str(row.get("from") or row.get("sender") or ""),
                           "recipient": recipient, "timestamp": ts,
                           "date": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts is not None else ""})
        result.sort(key=lambda item: item["timestamp"] or 0, reverse=True)
        return result[:limit]
