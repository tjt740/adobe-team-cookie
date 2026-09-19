"""交付对账:删掉"已推送打标、但 Sub2 用 id/邮箱/cookie指纹都找不到"的僵尸子号
(token/cookie 分叉或被 Sub2 因真实失败踢掉),踢母号组织+删本地→露缺口→自愈建新真号补。
安全阀:Sub2 不可达/指纹集空/超删除上限一律中止,绝不在抖动时误删。
env: AGE_HOURS(僵尸最小年龄,默认2)、ZOMBIE_CAP(单次删除上限,默认15)、EXECUTE=1 才真删。"""
import datetime
import hashlib
import json
import os
import sys

sys.path.insert(0, "/opt/adobeteam/backend")
os.chdir("/opt/adobeteam/backend")
from app.api.routes.sub2 import _existing_keys, _get_config, _member_dedup_keys
from app.crud import setting as setting_crud
from app.db.session import SessionLocal
from app.models.adobe_account import AdobeAccount
from app.models.adobe_member import AdobeMember
from app.services import adobe_admin, proxy_pool, sub2_client
from sqlalchemy import select

AGE_HOURS = float(os.environ.get("AGE_HOURS", "2"))
ZOMBIE_CAP = int(os.environ.get("ZOMBIE_CAP", "15"))
EXECUTE = os.environ.get("EXECUTE") == "1" or "execute" in sys.argv


def fp(cookie):
    v = {}
    for part in (cookie or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        n, val = part.split("=", 1)
        n = n.strip()
        if n:
            v[n] = val.strip()
    return hashlib.sha256("".join("%s=%s;" % (k, v[k]) for k in sorted(v)).encode()).hexdigest() if v else ""


d = SessionLocal()
cfg = _get_config(d)
plat = cfg.get("platform") or ""
ex = _existing_keys(cfg)
if not ex.get("ok"):
    print("Sub2 网关不可达,中止(不在抖动时删)"); sys.exit(0)
ex_ids, ex_em = ex.get("account_ids", set()), ex.get("emails", set())
sub2_fps = set()
base, token = sub2_client.api_base(cfg.get("base_url", "")), cfg.get("admin_token", "")
page = 1
while True:
    url = f"{base}/admin/accounts?page={page}&page_size=100" + (f"&platform={plat}" if plat else "")
    try:
        code, raw = sub2_client._request("GET", url, token, timeout=30)
        dd = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        print("拉 Sub2 指纹异常,中止:", str(e)[:80]); sys.exit(0)
    dd = dd.get("data") if isinstance(dd, dict) else dd
    items = dd.get("items") if isinstance(dd, dict) else dd
    if not items:
        break
    for a in items:
        c = a.get("credentials") if isinstance(a.get("credentials"), dict) else {}
        f = str(c.get("adobe_cookie_fingerprint") or "").strip()
        if f:
            sub2_fps.add(f)
    if len(items) < 100:
        break
    page += 1
if not sub2_fps:
    print("Sub2 指纹集为空(拉取异常?),中止"); sys.exit(0)

cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=AGE_HOURS)
zombies = []
for m in d.scalars(select(AdobeMember).where(
        AdobeMember.is_admin == False, AdobeMember.registered == True,  # noqa: E712
        AdobeMember.cookie != "", AdobeMember.sub2_pushed_at.isnot(None))):
    if m.created_at and m.created_at > cutoff:
        continue
    ids, email = _member_dedup_keys(m)
    if bool(ids & ex_ids) or (email in ex_em) or (fp(m.cookie) in sub2_fps):
        continue
    zombies.append(m)

print("Sub2 在线 ids=%d fps=%d | 僵尸(打标+Sub2无+年龄>%.1fh): %d" % (len(ex_ids), len(sub2_fps), AGE_HOURS, len(zombies)))
for m in zombies[:20]:
    print("  子号#%s %s 母号#%s credits=%s" % (m.id, (m.email or "")[:26], m.admin_id, m.credits))
if len(zombies) > ZOMBIE_CAP:
    print("!! 数量 %d 超安全上限 %d(疑 Sub2 拉取异常),中止,需人工核查" % (len(zombies), ZOMBIE_CAP)); sys.exit(0)
if not EXECUTE:
    print("[dry-run] 设 EXECUTE=1 或加 execute 才真删")
    sys.exit(0)

st = setting_crud.get_settings(d)
proxy_raw = st.proxy_url if (st.proxy_enabled and (st.proxy_url or "").strip()) else ""
admins = {a.id: a for a in d.scalars(select(AdobeAccount))}
deleted = 0
for m in zombies:
    acc = admins.get(m.admin_id)
    if acc and acc.admin_token and acc.org_id:
        for px in ([proxy_pool.next_proxy(proxy_raw) for _ in range(2)] if proxy_raw else []) + [""]:
            try:
                rr = adobe_admin.remove_member(token=acc.admin_token, org_id=acc.org_id, email=m.email, proxy_url=px)
                if rr.get("ok") or "未找到" in (rr.get("message") or ""):
                    break
            except Exception:  # noqa: BLE001
                continue
    d.delete(m)
    deleted += 1
d.commit()
print("对账完成:删僵尸 %d(踢母号组织+删本地)→母号露缺口→自愈建新真号补" % deleted)
d.close()
