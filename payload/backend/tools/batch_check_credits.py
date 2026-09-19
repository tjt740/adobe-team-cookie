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
from app.services import firefly_ios  # noqa: E402


def _iter_dicts(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            return [x for x in data["items"] if isinstance(x, dict)]
        return [data]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _load_file(path: Path) -> list[dict[str, Any]]:
    """Return list of {name, access_token, cookie} records from one file."""
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return []
    records: list[dict[str, Any]] = []
    try:
        data = json.loads(raw)
        for obj in _iter_dicts(data):
            token = str(obj.get("access_token") or "").strip()
            name = str(
                obj.get("name")
                or obj.get("email")
                or obj.get("display_name")
                or ""
            ).strip()
            cookie = str(obj.get("cookie") or obj.get("cookies") or "").strip()
            records.append({
                "name": name,
                "access_token": token,
                "cookie": cookie,
                "device_token": str(obj.get("device_token") or "").strip(),
                "device_id": str(obj.get("device_id") or "").strip(),
            })
    except json.JSONDecodeError:
        # one access_token (or cookie) per line
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("eyJ") and line.count(".") >= 2:
                records.append({"name": "", "access_token": line, "cookie": ""})
            else:
                records.append({"name": "", "access_token": "", "cookie": line})
    return records


def _check_one(rec: dict[str, Any], proxy: str, refresh: bool) -> dict[str, Any]:
    import time

    token = rec.get("access_token") or ""
    acct = firefly.extract_account_id(token) if token else ""
    name = rec.get("name") or acct or "?"
    out = {
        "name": name,
        "account_id": acct,
        "source": rec.get("source", ""),
        "credits": None,
        "status": "",
        "refreshed": False,
    }
    if not token:
        out["status"] = "no_token"  # cookie-only / needs conversion
        return out
    exp = firefly.extract_jwt_expiry(token)
    expired = bool(exp and exp < time.time())
    if expired:
        dt = rec.get("device_token") or ""
        did = rec.get("device_id") or ""
        if refresh and dt and did:
            try:
                res = firefly_ios.refresh_with_device_token(
                    device_token=dt, device_id=did, proxy_url=proxy
                )
                token = res.get("access_token") or ""
                acct = firefly.extract_account_id(token) or acct
                out["refreshed"] = True
            except Exception as exc:  # noqa: BLE001
                out["status"] = "refresh_failed"
                out["error"] = str(exc)[:160]
                return out
        else:
            out["status"] = "token_expired"  # 无 device_token,无法刷新
            return out
    credits = firefly.fetch_credits(token, account_id=acct, proxy_url=proxy)
    out["credits"] = credits
    if credits is None:
        out["status"] = "query_failed"
    elif credits > 0:
        out["status"] = "has_credits"
    else:
        out["status"] = "zero"
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="批量检测 Adobe 号是否还有积分(直接用 access_token 实时查 Firefly 余额)。"
    )
    parser.add_argument("inputs", nargs="+", help="一个或多个导出文件(json / txt)")
    parser.add_argument("--proxy", default="", help="可选代理,例如 http://user:pass@host:port")
    parser.add_argument("--workers", type=int, default=12, help="并发数,默认 12")
    parser.add_argument("-o", "--output", default="", help="结果 JSON 输出路径")
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="过期 token 不要用 device_token 刷新(默认会刷新)",
    )
    args = parser.parse_args()
    refresh = not args.no_refresh

    # collect + dedup by account_id (keep the record we see first per account)
    seen: dict[str, dict[str, Any]] = {}
    no_token: list[dict[str, Any]] = []
    total_rows = 0
    for p in args.inputs:
        path = Path(p)
        if not path.exists():
            print(f"[skip] 文件不存在: {p}", flush=True)
            continue
        recs = _load_file(path)
        for r in recs:
            total_rows += 1
            r["source"] = path.name
            token = r.get("access_token") or ""
            if not token:
                no_token.append(r)
                continue
            acct = firefly.extract_account_id(token)
            key = acct or token[:40]
            if key not in seen:
                seen[key] = r
        print(f"[load] {path.name}: {len(recs)} 行", flush=True)

    targets = list(seen.values())
    print(
        f"\n总行数 {total_rows} | 去重后待查 {len(targets)} | "
        f"无 token(cookie/需转换) {len(no_token)}\n",
        flush=True,
    )

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(_check_one, r, args.proxy, refresh): r for r in targets}
        done = 0
        for fut in as_completed(futs):
            res = fut.result()
            results.append(res)
            done += 1
            mark = {
                "has_credits": "OK ",
                "zero": "0  ",
                "query_failed": "FAIL",
                "token_expired": "EXP",
                "refresh_failed": "RFL",
                "no_token": "----",
            }.get(res["status"], "?")
            rf = "*" if res.get("refreshed") else " "
            print(
                f"[{done}/{len(targets)}] {mark}{rf} {res['name']:<42} "
                f"credits={res['credits']}",
                flush=True,
            )

    has = [r for r in results if r["status"] == "has_credits"]
    zero = [r for r in results if r["status"] == "zero"]
    failed = [r for r in results if r["status"] == "query_failed"]
    expired = [r for r in results if r["status"] == "token_expired"]
    refresh_failed = [r for r in results if r["status"] == "refresh_failed"]
    refreshed_n = sum(1 for r in results if r.get("refreshed"))
    has.sort(key=lambda r: (r["credits"] or 0), reverse=True)

    print("\n========== 汇总 ==========", flush=True)
    print(f"有积分 : {len(has)}  (其中刷新后查到 {sum(1 for r in has if r.get('refreshed'))})", flush=True)
    print(f"0 积分 : {len(zero)}", flush=True)
    print(f"已刷新 token 总数: {refreshed_n}", flush=True)
    print(f"刷新失败(device_token 失效): {len(refresh_failed)}", flush=True)
    print(f"过期且无 device_token(无法刷新): {len(expired)}", flush=True)
    print(f"查询失败(网络): {len(failed)}", flush=True)
    print(f"cookie/无token(未查): {len(no_token)}", flush=True)
    total_credits = sum((r["credits"] or 0) for r in has)
    print(f"有积分账号总额度: {total_credits:.0f}", flush=True)

    print("\n---------- 有积分账号 ----------", flush=True)
    for r in has:
        print(f"  {r['credits']:>8.0f}  {r['name']}", flush=True)

    if args.output:
        payload = {
            "summary": {
                "total_rows": total_rows,
                "checked": len(targets),
                "has_credits": len(has),
                "zero": len(zero),
                "refreshed": refreshed_n,
                "refresh_failed": len(refresh_failed),
                "token_expired_no_dt": len(expired),
                "query_failed": len(failed),
                "no_token": len(no_token),
                "total_credits": total_credits,
            },
            "has_credits": has,
            "zero": zero,
            "refresh_failed": refresh_failed,
            "token_expired": expired,
            "query_failed": failed,
            "no_token": [
                {"name": r.get("name"), "source": r.get("source")} for r in no_token
            ],
        }
        Path(args.output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nsaved: {args.output}", flush=True)


if __name__ == "__main__":
    main()
