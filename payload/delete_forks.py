import sys, os, json, time, datetime
sys.path.insert(0, "/opt/adobeteam/backend")
os.chdir("/opt/adobeteam/backend")
from app.db.session import SessionLocal
from sqlalchemy import select
from app.models.adobe_account import AdobeAccount
from app.api.routes.sub2 import _get_config, _existing_keys, _candidates
from app.services import adobe_admin, proxy_pool
from app.crud import setting as setting_crud

EXECUTE = "execute" in sys.argv
d = SessionLocal()
cfg = _get_config(d)
ex = _existing_keys(cfg)
if not ex.get("ok"):
    print("⚠ Sub2 网关不可达,中止(无法确认待推)"); sys.exit(1)
rows, _in = _candidates(d, ex, None, platform=cfg.get("platform"))
cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
forks = [m for m in rows if m.created_at and m.created_at < cutoff]
print("待推总 %d · 待删分叉(待推>1h) %d · 保留新号(<1h) %d" % (len(rows), len(forks), len(rows) - len(forks)))
if not EXECUTE:
    for m in forks[:12]:
        print("  子号#%s %s 母号#%s" % (m.id, (m.email or "")[:26], m.admin_id))
    print("[dry-run] 加 execute 真删")
    sys.exit(0)

ts = time.strftime("%Y%m%d_%H%M%S")
bk = "/opt/adobeteam/_bk_forks_%s.json" % ts
json.dump([{"id": m.id, "email": m.email, "admin_id": m.admin_id} for m in forks],
          open(bk, "w"), ensure_ascii=False)
print("✓ 备份 →", bk)

st = setting_crud.get_settings(d)
proxy_raw = st.proxy_url if (st.proxy_enabled and (st.proxy_url or "").strip()) else ""
admins = {a.id: a for a in d.scalars(select(AdobeAccount))}
kicked = deleted = 0
for m in forks:
    acc = admins.get(m.admin_id)
    if acc and acc.admin_token and acc.org_id:
        for px in ([proxy_pool.next_proxy(proxy_raw) for _ in range(2)] if proxy_raw else []) + [""]:
            try:
                rr = adobe_admin.remove_member(token=acc.admin_token, org_id=acc.org_id,
                                               email=m.email, proxy_url=px)
                if rr.get("ok") or "未找到" in (rr.get("message") or ""):
                    kicked += 1; break
            except Exception:
                continue
    d.delete(m); deleted += 1
d.commit()
print("✓ 踢出母号组织 %d · 删本地子号行 %d" % (kicked, deleted))
print("=== 完成,母号会露出缺口、下轮自愈建真号补上 ===")
