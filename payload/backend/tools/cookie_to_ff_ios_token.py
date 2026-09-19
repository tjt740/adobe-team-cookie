from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.adobe_protocol.http_client import HttpClient  # noqa: E402
from app.services import firefly  # noqa: E402
from app.services.firefly_ios import (  # noqa: E402
    FireflyIOSError,
    mint_ff_ios_device_token,
    new_device_id,
)


COOKIE_DOMAINS = (
    "",
    ".adobe.com",
    "adobe.com",
    ".services.adobe.com",
    "services.adobe.com",
    "auth.services.adobe.com",
    "adobeid-na1.services.adobe.com",
    "ims-na1.adobelogin.com",
    "firefly.adobe.com",
)


def _load_items(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        items: list[dict[str, Any]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                items.append(json.loads(line))
            else:
                items.append({"cookie": line})
        return items
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            return [x for x in data["items"] if isinstance(x, dict)]
        return [data]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    raise SystemExit("输入必须是 JSON object / JSON array / 每行一个 cookie")


def _cookie_pairs(cookie: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (cookie or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, val = part.split("=", 1)
        key = key.strip()
        if key:
            out[key] = val.strip()
    return out


def _seed_cookie(client: HttpClient, cookie: str) -> None:
    pairs = _cookie_pairs(cookie)
    if not pairs:
        raise FireflyIOSError("cookie 为空或格式无效")
    client.cookies.update(pairs)
    jar = getattr(client.session, "cookies", None)
    if jar is None:
        return
    for key, val in pairs.items():
        try:
            jar.set(key, val)
        except Exception:
            pass
        for domain in COOKIE_DOMAINS:
            if not domain:
                continue
            try:
                jar.set(key, val, domain=domain, path="/")
            except Exception:
                pass


def convert_one(item: dict[str, Any], *, proxy: str = "", fetch_credits: bool = True) -> dict[str, Any]:
    cookie = str(item.get("cookie") or "").strip()
    email = str(item.get("email") or item.get("name") or "").strip()
    device_id = str(item.get("device_id") or "").strip() or new_device_id()
    client = HttpClient(proxy=proxy)
    try:
        _seed_cookie(client, cookie)
        rec = mint_ff_ios_device_token(
            client,
            "",
            email or "cookie_account",
            device_id=device_id,
            proxy_url=proxy,
            log=print,
        )
        token = rec.get("access_token") or ""
        credits = None
        if fetch_credits and token:
            credits = firefly.fetch_credits(token, proxy_url=proxy)
        return {
            "cookie": "",
            "name": email or rec.get("user_id") or "cookie_account",
            "access_token": token,
            "device_token": rec.get("device_token") or "",
            "device_id": rec.get("device_id") or device_id,
            "arp_session_id": "",
            "credits": credits,
            "expires_at": rec.get("expires_at"),
        }
    finally:
        client.close()


def _format_result(rec: dict[str, Any], output_format: str) -> dict[str, Any]:
    """Normalize converted token into a target import format."""
    if output_format == "newbanana":
        return {
            "name": rec.get("name") or "cookie_account",
            "cookie": rec.get("cookie") or "",
            "access_token": rec.get("access_token") or "",
            "device_token": rec.get("device_token") or "",
            "device_id": rec.get("device_id") or "",
            "arp_session_id": rec.get("arp_session_id") or "",
            "credits": rec.get("credits") or 0,
            "expires_at": rec.get("expires_at") or 0,
        }
    return rec


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Adobe browser cookies into FF-iOS access_token/device_token."
    )
    parser.add_argument("input", help="包含 cookie 字段的 JSON 文件,或每行一个 cookie 的 txt")
    parser.add_argument("-o", "--output", default="", help="输出 JSON 文件路径")
    parser.add_argument("--proxy", default="", help="可选代理,例如 http://user:pass@host:port")
    parser.add_argument("--no-credits", action="store_true", help="只换 token,不查询额度")
    parser.add_argument(
        "--output-format",
        choices=("okad", "newbanana"),
        default="okad",
        help="输出格式: okad=本系统号池格式; newbanana=newbanana Cookie 批量导入格式",
    )
    parser.add_argument(
        "--array",
        action="store_true",
        help="即使只有一条结果也输出 JSON 数组",
    )
    args = parser.parse_args()

    items = _load_items(Path(args.input))
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for idx, item in enumerate(items, start=1):
        label = str(item.get("email") or item.get("name") or f"#{idx}")
        try:
            print(f"=== {idx}/{len(items)} {label} ===", flush=True)
            rec = convert_one(item, proxy=args.proxy, fetch_credits=not args.no_credits)
            results.append(
                _format_result(rec, args.output_format)
            )
            print(f"OK {label}", flush=True)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)[:500]
            errors.append({"item": label, "error": msg})
            print(f"FAIL {label}: {msg}", flush=True)

    payload: Any = results if (args.array or args.output_format == "newbanana" or len(results) != 1) else results[0]
    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"saved: {args.output}", flush=True)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    if errors:
        print("errors:", json.dumps(errors, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
