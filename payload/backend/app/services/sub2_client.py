"""与 Sub2API 网关对接:把 AdobeTeam 号池里的子号推送为 Adobe 账号。

只依赖标准库(urllib),避免额外依赖。配置由调用方以 dict 传入:
  base_url / admin_token / platform / protocol / group_ids / name_prefix / rate_multiplier
"""
from __future__ import annotations

import json

from app.services.adobe_protocol.http_client import HttpClient


def api_base(base_url: str) -> str:
    """归一到 Sub2API 的 v1 前缀:{host}/api/v1(无论用户填到主机、/api 还是 /api/v1)。"""
    b = (base_url or "").strip().rstrip("/")
    if not b:
        return ""
    for suffix in ("/api/v1", "/api", "/v1"):
        if b.endswith(suffix):
            b = b[: -len(suffix)]
            break
    return b + "/api/v1"


def _safe_float(v, default: float) -> float:
    try:
        f = float(v)
        return f if f >= 0 else default
    except (TypeError, ValueError):
        return default


def _auth_headers(token: str) -> dict:
    """admin- 开头=管理员 API Key,走 x-api-key;否则当 JWT 走 Authorization: Bearer。"""
    token = (token or "").strip()
    if token.startswith("admin-"):
        return {"x-api-key": token}
    return {"Authorization": f"Bearer {token}"}


def _request(method: str, url: str, token: str, body=None, timeout: int = 40):
    """用 curl_cffi 的 Chrome 指纹发请求,绕过 Sub2API 前置 Cloudflare 的浏览器指纹校验
    (纯 urllib/requests 会被 Cloudflare Error 1010 browser_signature_banned 拦掉)。"""
    client = HttpClient(proxy="")
    try:
        headers = {"Accept": "application/json", **_auth_headers(token)}
        m = method.upper()
        if m == "GET":
            r = client.get(url, headers=headers, allow_redirects=True, timeout=timeout)
        elif m == "DELETE":
            h = client._base_headers()
            h.update(headers)
            r = client.session.delete(url, headers=h, timeout=timeout)
        else:
            r = client.post(url, headers=headers, json=body, allow_redirects=True, timeout=timeout)
        return r.status_code, (r.text or "")
    finally:
        client.close()


def test_connection(cfg: dict) -> dict:
    base = api_base(cfg.get("base_url", ""))
    token = cfg.get("admin_token", "")
    if not base or not token:
        return {"ok": False, "message": "尚未配置 base_url 或 admin_token"}
    url = f"{base}/admin/accounts?page=1&page_size=1"
    try:
        code, body = _request("GET", url, token, timeout=20)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"连接失败:{e}"}
    if code == 200:
        return {"ok": True, "message": "连接成功,令牌有效"}
    if code in (400, 422):
        return {"ok": True, "message": f"连接成功(令牌有效,列表接口 HTTP {code})"}
    if code in (401, 403):
        return {"ok": False, "message": f"鉴权失败 (HTTP {code}),请检查 admin token 与地址"}
    if code == 404:
        return {"ok": False, "message": "端点 404:请检查 Sub2API 地址(需能到 /api/v1)"}
    return {"ok": False, "message": f"可达但返回 HTTP {code}:{body[:160]}"}


def list_groups(cfg: dict) -> dict:
    """列出 Sub2API 的全部分组(用于配置里选择绑定分组)。"""
    base = api_base(cfg.get("base_url", ""))
    token = cfg.get("admin_token", "")
    if not base or not token:
        return {"ok": False, "message": "尚未配置 base_url 或 admin_token", "groups": []}
    try:
        code, raw = _request("GET", f"{base}/admin/groups/all", token, timeout=20)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"连接失败:{e}", "groups": []}
    if code != 200:
        return {"ok": False, "message": f"获取分组失败 HTTP {code}", "groups": []}
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return {"ok": False, "message": "分组响应解析失败", "groups": []}
    items = data.get("data") if isinstance(data, dict) else data
    if isinstance(items, dict):
        items = items.get("items") or items.get("groups") or []
    groups = []
    for g in items or []:
        if isinstance(g, dict) and g.get("id") is not None:
            groups.append({"id": g.get("id"), "name": g.get("name") or str(g.get("id")),
                           "platform": g.get("platform") or ""})
    return {"ok": True, "groups": groups}


def list_existing(cfg: dict, platform: str = "", max_pages: int = 200, page_size: int = 100) -> dict:
    """拉取 Sub2API 已有账号的 account_id/邮箱集合(推送前去重)。

    任何一页拉取失败(网络/非200/解析失败)都返回 ok=False——绝不把"拉取失败"
    伪装成"0 账号",否则去重会被静默关闭导致重复推送。
    """
    base = api_base(cfg.get("base_url", ""))
    token = cfg.get("admin_token", "")
    account_ids: set[str] = set()
    emails: set[str] = set()
    if not base or not token:
        return {"ok": False, "account_ids": account_ids, "emails": emails, "count": 0, "message": "未配置"}
    page, fetched, truncated = 1, 0, False
    while True:
        if page > max_pages:
            truncated = True
            break
        url = f"{base}/admin/accounts?page={page}&page_size={page_size}"
        if platform:
            url += f"&platform={platform}"
        try:
            code, raw = _request("GET", url, token, timeout=30)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "account_ids": set(), "emails": set(), "count": 0, "message": f"连接失败:{e}"[:160]}
        if code != 200:
            return {"ok": False, "account_ids": set(), "emails": set(), "count": 0, "message": f"HTTP {code}"}
        try:
            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            return {"ok": False, "account_ids": set(), "emails": set(), "count": 0, "message": "响应解析失败"}
        d = data.get("data") if isinstance(data, dict) else data
        items = d.get("items") if isinstance(d, dict) else (d if isinstance(d, list) else [])
        if not items:
            break
        for a in items:
            if not isinstance(a, dict):
                continue
            if platform and a.get("platform") != platform:
                continue
            creds = a.get("credentials") if isinstance(a.get("credentials"), dict) else {}
            aid = str(creds.get("account_id") or "").strip()
            if aid:
                account_ids.add(aid)
            # 邮箱去重键:优先 credentials.email(Sub2 真存处),回退 name/refresh_profile_email。
            # 早期只读顶层 name(多为显示名如"Aaron Harris")→ 166 账号只抓到 1 个 email,兜底失效。
            for cand_em in (creds.get("email"), a.get("name"), creds.get("refresh_profile_email")):
                em = str(cand_em or "").strip().lower()
                if "@" in em:
                    emails.add(em)
        fetched += len(items)
        total = d.get("total") if isinstance(d, dict) else None
        if isinstance(total, int) and fetched >= total:
            break
        if len(items) < page_size:
            break
        page += 1
    return {"ok": True, "account_ids": account_ids, "emails": emails,
            "count": len(account_ids), "truncated": truncated}


def list_accounts_full(cfg: dict, platform: str = "", max_pages: int = 200, page_size: int = 100) -> dict:
    """拉 Sub2 全量账号记录(含 Sub2 数字 id、name/邮箱、Adobe account_id),用于测活+删除。"""
    base = api_base(cfg.get("base_url", ""))
    token = cfg.get("admin_token", "")
    out: list[dict] = []
    if not base or not token:
        return {"ok": False, "accounts": out, "message": "未配置"}
    page, fetched, truncated = 1, 0, False
    while True:
        if page > max_pages:
            truncated = True
            break
        url = f"{base}/admin/accounts?page={page}&page_size={page_size}"
        if platform:
            url += f"&platform={platform}"
        try:
            code, raw = _request("GET", url, token, timeout=30)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "accounts": [], "message": f"连接失败:{e}"[:160]}
        if code != 200:
            return {"ok": False, "accounts": [], "message": f"HTTP {code}"}
        try:
            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            return {"ok": False, "accounts": [], "message": "响应解析失败"}
        d = data.get("data") if isinstance(data, dict) else data
        items = d.get("items") if isinstance(d, dict) else (d if isinstance(d, list) else [])
        if not items:
            break
        for a in items:
            if not isinstance(a, dict):
                continue
            if platform and a.get("platform") != platform:
                continue
            creds = a.get("credentials") if isinstance(a.get("credentials"), dict) else {}
            nm = str(a.get("name") or "").strip()
            out.append({
                "id": a.get("id"),
                "name": nm,
                "email": nm.lower() if "@" in nm else "",
                "account_id": str(creds.get("account_id") or "").strip(),
            })
        fetched += len(items)
        total = d.get("total") if isinstance(d, dict) else None
        if isinstance(total, int) and fetched >= total:
            break
        if len(items) < page_size:
            break
        page += 1
    return {"ok": True, "accounts": out, "truncated": truncated}


def list_accounts_page(cfg: dict, platform: str = "", page: int = 1, size: int = 50) -> dict:
    """分页列 Sub2 账号(给管理表格用),返回精简字段 + total。"""
    base = api_base(cfg.get("base_url", ""))
    token = cfg.get("admin_token", "")
    if not base or not token:
        return {"ok": False, "items": [], "total": 0, "message": "未配置"}
    url = f"{base}/admin/accounts?page={page}&page_size={size}"
    if platform:
        url += f"&platform={platform}"
    try:
        code, raw = _request("GET", url, token, timeout=30)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "items": [], "total": 0, "message": str(e)[:120]}
    if code != 200:
        return {"ok": False, "items": [], "total": 0, "message": f"HTTP {code}"}
    try:
        d = json.loads(raw)
    except Exception:  # noqa: BLE001
        return {"ok": False, "items": [], "total": 0, "message": "解析失败"}
    data = d.get("data") if isinstance(d, dict) else d
    items = data.get("items") if isinstance(data, dict) else (data if isinstance(data, list) else [])
    total = data.get("total") if isinstance(data, dict) else len(items or [])
    out = []
    for a in items or []:
        if not isinstance(a, dict):
            continue
        if platform and a.get("platform") != platform:
            continue
        creds = a.get("credentials") if isinstance(a.get("credentials"), dict) else {}
        extra = a.get("extra") if isinstance(a.get("extra"), dict) else {}
        cs = a.get("credentials_status") if isinstance(a.get("credentials_status"), dict) else {}
        out.append({
            "id": a.get("id"),
            "name": a.get("name") or "",
            "status": a.get("status") or "",
            "schedulable": a.get("schedulable"),
            "error": a.get("error_message") or "",
            "last_used_at": a.get("last_used_at"),
            "last_refresh_at": creds.get("last_refresh_at"),
            "token_exp": creds.get("token_exp") or creds.get("expires_at"),
            "auto_refresh": creds.get("auto_refresh"),
            "account_id": str(creds.get("account_id") or ""),
            "group_ids": a.get("group_ids") or [],
            "cap1k": extra.get("adobe_capability_1k"),
            "cap2k": extra.get("adobe_capability_2k"),
            "cap4k": extra.get("adobe_capability_4k"),
            "cap_msg": extra.get("adobe_capability_last_message") or "",
            "balance_status": extra.get("adobe_balance_last_status") or "",
            "balance_at": extra.get("adobe_balance_checked_at"),
            "credits_avail": extra.get("adobe_credits_available"),
            "credits_total": extra.get("adobe_credits_total"),
            "credits_used": extra.get("adobe_credits_used"),
            "credits_until": extra.get("adobe_credits_available_until"),
            "fails": extra.get("adobe_consecutive_failures"),
            "has_token": cs.get("has_token"),
        })
    return {"ok": True, "items": out, "total": total}


def batch_refresh(cfg: dict, account_ids: list, balance: bool = False) -> dict:
    """调 Sub2 自己的批量刷新(cookie 刷新 token / 刷额度)。"""
    base = api_base(cfg.get("base_url", ""))
    token = cfg.get("admin_token", "")
    path = "balance-refresh-batch" if balance else "token-refresh-batch"
    url = f"{base}/admin/accounts/adobe/{path}"
    body = {"account_ids": account_ids, "platform": cfg.get("platform") or ""}
    try:
        code, raw = _request("POST", url, token, body=body, timeout=180)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "code": 0, "message": str(e)[:140]}
    try:
        d = json.loads(raw)
    except Exception:  # noqa: BLE001
        d = {"raw": raw[:400]}
    result = d.get("data") if isinstance(d, dict) and isinstance(d.get("data"), dict) else d
    return {"ok": code == 200, "code": code, "result": result,
            "message": (d.get("message") if isinstance(d, dict) else "")}


def delete_account(cfg: dict, sub2_id) -> dict:
    base = api_base(cfg.get("base_url", ""))
    token = cfg.get("admin_token", "")
    try:
        code, raw = _request("DELETE", f"{base}/admin/accounts/{sub2_id}", token, timeout=30)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "code": 0, "message": str(e)[:140]}
    return {"ok": code in (200, 204), "code": code}


def import_tokens(cfg: dict, items: list[dict]) -> dict:
    """把 items(号池子号)以 **cookie** 方式导入 Sub2(/admin/accounts/adobe/import-cookie)。

    关键:必须用 cookie 导入,Sub2 会从 cookie 提取 ims_sid、建成 protocol=express 的账号
    并自行铸造/刷新 token(可持续用);早期误用 import-token(access_token)只会生成
    "Token 手动"静态账号,token 过期即失效——那种加法不能用。
    只有带 cookie 的子号能这样导入;无 cookie 的(仅 device_token)会被跳过并计入 skipped。
    返回 {code, result, message},result 尽量归一为 AdobeImportResult 结构(含 skipped)。
    """
    base = api_base(cfg.get("base_url", ""))
    token = cfg.get("admin_token", "")
    url = f"{base}/admin/accounts/adobe/import-cookie"
    content_objs = []
    skipped = 0
    for it in items:
        ck = (it.get("cookie") or "").strip()
        if not ck:
            skipped += 1
            continue
        content_objs.append({
            "name": it.get("name") or it.get("email") or "",
            "cookie": ck,
            "credits": it.get("credits"),
            "expires_at": it.get("expires_at"),
        })
    if not content_objs:
        return {"code": 0, "result": {"created": 0, "failed": 0, "skipped": skipped},
                "message": "无可导入子号(均无 cookie)"}
    body = {
        "platform": cfg.get("platform") or "adobe_gemini",
        "protocol": cfg.get("protocol") or "default",
        "content": json.dumps(content_objs, ensure_ascii=False),
        "name": cfg.get("name_prefix") or "",
        "group_ids": cfg.get("group_ids") or [],
        "concurrency": int(cfg.get("concurrency") or 18),
        "priority": 0,
        "rate_multiplier": _safe_float(cfg.get("rate_multiplier"), 1.0),
    }
    try:
        # cookie 导入要现场铸 token,较慢,给到 300s(与前端一致)
        code, raw = _request("POST", url, token, body=body, timeout=300)
    except Exception as e:  # noqa: BLE001
        return {"code": 0, "result": {}, "message": f"导入请求失败:{e}"[:160]}
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        data = {"raw": raw[:600]}
    # Sub2API 常见响应外层 {code,message,data}; 归一到 AdobeImportResult
    result = data
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        result = data["data"]
    if isinstance(result, dict):
        result.setdefault("skipped", skipped)
    return {"code": code, "result": result, "message": (data.get("message") if isinstance(data, dict) else "")}
