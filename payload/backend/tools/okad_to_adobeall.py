from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import firefly  # noqa: E402


def _to_ms(ts: Any) -> int:
    """Normalize an epoch (s or ms) into milliseconds."""
    try:
        v = int(ts)
    except (TypeError, ValueError):
        return 0
    if v <= 0:
        return 0
    # 10 位=秒,13 位=毫秒
    return v * 1000 if v < 10_000_000_000 else v


def _looks_email(s: str) -> bool:
    return "@" in s and not s.endswith("@AdobeID")


def _build(rec: dict[str, Any], proxy: str) -> dict[str, Any]:
    token = rec.get("access_token") or ""
    acct = firefly.extract_account_id(token)
    name = (rec.get("name") or "").strip()
    info = firefly.fetch_account_info(token, proxy_url=proxy) if token else {}
    email = (info.get("email") or "").strip()
    if not email and _looks_email(name):
        email = name
    display_name = (info.get("display_name") or "").strip()
    user_id = (info.get("user_id") or acct or "").strip()
    return {
        "email": email or user_id,
        "display_name": display_name,
        "adobe_user_id": user_id,
        "access_token": token,
        "device_token": rec.get("device_token") or "",
        "device_id": rec.get("device_id") or "",
        "status": "valid",
        "source": "import",
        "credits": rec.get("credits") if rec.get("credits") is not None else 0,
        "expires_at": _to_ms(rec.get("expires_at")),
        "refresh_enabled": 1,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="把 okad 号池格式(name/access_token/...) 转成 adobe-all 导入格式(email/adobe_user_id/...)。"
    )
    ap.add_argument("input", help="okad 格式的 JSON 文件(数组)")
    ap.add_argument("-o", "--output", required=True, help="输出 JSON 文件")
    ap.add_argument("--proxy", default="", help="可选代理")
    ap.add_argument("--workers", type=int, default=12, help="并发数,默认 12")
    args = ap.parse_args()

    data = json.load(open(args.input, encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("items") or [data]
    records = [x for x in data if isinstance(x, dict) and (x.get("access_token"))]
    print(f"待转换 {len(records)} 条", flush=True)

    out: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(_build, r, args.proxy): r for r in records}
        done = 0
        for fut in as_completed(futs):
            res = fut.result()
            out.append(res)
            done += 1
            print(f"[{done}/{len(records)}] {res['email']}  credits={res['credits']}", flush=True)

    Path(args.output).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    no_email = sum(1 for r in out if not _looks_email(r["email"]))
    print(f"\n完成 {len(out)} 条,其中未取到真实邮箱 {no_email} 条(用 user_id 占位)", flush=True)
    print(f"saved: {args.output}", flush=True)


if __name__ == "__main__":
    main()
