#!/usr/bin/env python3
"""组织已删(Deleted-Org)母号自动清理 —— 每日定时跑,安全:
- 登录 invalid 母号(代理轮换),【只在企业资料名含 'Deleted' 时】判为真死组织;
- type2e / 无企业资料链接 / 瞬时失败 一律跳过不删;
- 确认死组织的:删 Sub2 号 + 踢母号(组织已删踢不动无妨)+ 删本地子号/母号行;
- 删前备份到 JSON。默认 dry-run,传 execute 才真删。CAP 限量防慢。
用法:prune_dead_orgs.py [execute] [cap]
"""
import sys, os, io, contextlib, json, time
sys.path.insert(0, "/opt/adobeteam/backend")
os.chdir("/opt/adobeteam/backend")
from app.db.session import SessionLocal
from sqlalchemy import select, text
from app.models.adobe_account import AdobeAccount
from app.models.adobe_member import AdobeMember
from app.services import adobe_admin, proxy_pool, sub2_client
from app.crud import setting as setting_crud
from app.api.routes.sub2 import _get_config, _sub2_id_map, _member_account_id

EXECUTE = "execute" in sys.argv
CAP = 6
for a in sys.argv[1:]:
    if a.isdigit():
        CAP = int(a)
SKIP = ("type2e", "eoachoose")

d = SessionLocal()
st = setting_crud.get_settings(d)
proxy_raw = st.proxy_url if (st.proxy_enabled and (st.proxy_url or "").strip()) else ""

cands = d.scalars(select(AdobeAccount).where(
    AdobeAccount.is_valid.isnot(True), AdobeAccount.refresh_token != "",
    AdobeAccount.client_id != "")).all()
# 跳过 type2e;优先处理"疑似死组织"(check_message 提无组织的)
targets = [a for a in cands if not any(s in (a.check_message or "").lower() for s in SKIP)][:CAP]
print("=== 待核 %d 个 invalid 母号(execute=%s)===" % (len(targets), EXECUTE), flush=True)

dead = []
for acc in targets:
    prof = [""]
    def lf(m):
        s = str(m)
        if "选择企业资料" in s:
            prof[0] = s.split(":")[-1].strip()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            res = adobe_admin.login_account(
                email=acc.email, adobe_password=acc.adobe_password,
                refresh_token=acc.refresh_token, client_id=acc.client_id,
                proxy_url=proxy_pool.next_proxy(proxy_raw), otp_timeout=90, log=lf)
        if res.get("rotated_refresh_token"):
            acc.refresh_token = res["rotated_refresh_token"]; d.commit()
        if res.get("has_org"):
            print("  #%s %s ✅有组织(误判,恢复) org=%s" % (acc.id, acc.email[:26], res.get("org_id")), flush=True)
            acc.is_valid = True; acc.org_id = res.get("org_id") or ""; acc.admin_token = res.get("token") or ""
            acc.product_id = res.get("product_id") or ""; acc.license_group_id = res.get("license_group_id") or ""
            acc.has_org = True; d.commit()
        elif "Deleted" in prof[0]:
            print("  #%s %s 💀组织已删: %s" % (acc.id, acc.email[:26], prof[0]), flush=True)
            acc.check_message = ("组织已删除:" + prof[0])[:500]; d.commit()
            dead.append(acc)
        else:
            print("  #%s %s ⚠存疑(profile=%s),不删" % (acc.id, acc.email[:26], prof[0] or "无"), flush=True)
    except Exception as e:
        print("  #%s %s 🔁登录失败(不删): %s" % (acc.id, acc.email[:26], str(e)[:50]), flush=True)

print("=== 确认死组织 %d 个 ===" % len(dead), flush=True)
if not dead:
    print("无可删。"); sys.exit(0)
if not EXECUTE:
    print("[dry-run] 未删。加 execute 参数真删。"); sys.exit(0)

# 备份
ts = time.strftime("%Y%m%d_%H%M%S")
bk = "/opt/adobeteam/_bk_deadorg_%s.json" % ts
dead_ids = [a.id for a in dead]
subs = d.scalars(select(AdobeMember).where(AdobeMember.admin_id.in_(dead_ids), AdobeMember.is_admin == False)).all()  # noqa: E712
json.dump({"moms": [{"id": a.id, "email": a.email, "msg": a.check_message} for a in dead],
           "subs": [{"id": m.id, "email": m.email, "admin_id": m.admin_id} for m in subs]},
          open(bk, "w"), ensure_ascii=False, indent=1)
print("✓ 备份 →", bk, flush=True)

# 删 Sub2 上这些子号(若在库)
cfg = _get_config(d)
idmap = _sub2_id_map(cfg) or {}
s2del = 0
for m in subs:
    key = (_member_account_id(m) or (m.email or "").lower())
    sid = idmap.get(str(key).strip()) or idmap.get((m.email or "").lower())
    if sid:
        try:
            if sub2_client.delete_account(cfg, sid).get("ok"):
                s2del += 1
        except Exception:
            pass
print("✓ Sub2 删 %d 个子号" % s2del, flush=True)

# 删本地子号 + 母号
ph = ",".join(str(i) for i in dead_ids)
ns = d.execute(text("delete from adobe_members where admin_id in (%s)" % ph)).rowcount
nm = d.execute(text("delete from adobe_accounts where id in (%s)" % ph)).rowcount
d.commit()
print("✓ 本地删:成员行 %d · 母号 %d" % (ns, nm), flush=True)
print("=== 完成 ===", flush=True)
