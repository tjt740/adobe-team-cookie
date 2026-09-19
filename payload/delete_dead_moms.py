"""删除 10 个组织已删(Deleted-Org)的死母号 + 其子号(含 Sub2 清理)。
默认 dry-run 只报告;传 execute 才真删。执行前先备份母号+子号行到 JSON。"""
import sys, os, json, time
sys.path.insert(0, "/opt/adobeteam/backend")
os.chdir("/opt/adobeteam/backend")
from app.db.session import SessionLocal
from sqlalchemy import text
from app.api.routes.sub2 import _get_config, _sub2_id_map, _member_account_id
from app.services import sub2_client

DEAD = [4, 5, 8, 9, 11, 12, 14, 16, 17, 19]
EXECUTE = len(sys.argv) > 1 and sys.argv[1] == "execute"
d = SessionLocal()

# 1. 核对母号确是 Deleted-Org / 无效
print("=== 待删母号(核对)===")
moms = d.execute(text(
    "select id,email,is_valid,check_message from adobe_accounts where id in "
    "(4,5,8,9,11,12,14,16,17,19) order by id")).fetchall()
for m in moms:
    print("  #%s %s valid=%s | %s" % (m[0], m[1][:28], m[2], (m[3] or "")[:45]))
if len(moms) != 10:
    print("⚠ 母号数不是10(%d),中止" % len(moms)); sys.exit(1)
if any(m[2] == 1 for m in moms):
    print("⚠ 有母号 is_valid=1,中止(不删有效母号)"); sys.exit(1)

# 2. 子号 + Sub2 状态
subs = d.execute(text(
    "select id,email,admin_id,cookie,credits from adobe_members "
    "where admin_id in (4,5,8,9,11,12,14,16,17,19) and is_admin=0")).fetchall()
print("\n=== 子号 %d 个 + Sub2 状态 ===" % len(subs))
cfg = _get_config(d)
idmap = _sub2_id_map(cfg)  # {account_id/email -> sub2_id};网关失败=None
if idmap is None:
    print("⚠ Sub2 网关不可达,无法确认子号 Sub2 状态");
sub_plan = []
for s in subs:
    mid, email = s[0], (s[1] or "").strip().lower()
    m_obj = d.get(__import__("app.models.adobe_member", fromlist=["AdobeMember"]).AdobeMember, mid)
    aid = _member_account_id(m_obj) if m_obj else ""
    sub2_id = None
    if idmap:
        sub2_id = idmap.get(str(aid).strip()) or idmap.get(email)
    sub_plan.append((mid, email, s[2], sub2_id))
    print("  子号#%s %s (母号#%s) → Sub2 %s" % (
        mid, email[:30], s[2], ("live id=%s" % sub2_id) if sub2_id else "不在live池"))

print("\n=== 计划 ===")
print("删母号 10 个 · 删子号 %d 个 · 其中在 Sub2 live 需删 %d 个" % (
    len(subs), sum(1 for x in sub_plan if x[3])))

if not EXECUTE:
    print("\n[dry-run] 未执行。确认后加 execute 参数真删。")
    sys.exit(0)

# 3. 执行:先备份
ts = time.strftime("%Y%m%d_%H%M%S")
bk = "/opt/adobeteam/_bk_deadmoms_%s.json" % ts
backup = {
    "moms": [dict(zip(["id", "email", "is_valid", "check_message"], m)) for m in moms],
    "subs": [dict(zip(["id", "email", "admin_id", "has_cookie", "credits"],
                      (s[0], s[1], s[2], bool(s[3]), s[4]))) for s in subs],
    "sub_plan": [{"member_id": x[0], "email": x[1], "admin_id": x[2], "sub2_id": x[3]} for x in sub_plan],
}
json.dump(backup, open(bk, "w"), ensure_ascii=False, indent=1)
print("✓ 备份 → %s" % bk)

# 4. 删 Sub2 live 子号
sub2_deleted = 0
for mid, email, admin_id, sub2_id in sub_plan:
    if sub2_id:
        try:
            r = sub2_client.delete_account(cfg, sub2_id)
            if r.get("ok"):
                sub2_deleted += 1
            else:
                print("  ⚠ Sub2 删 id=%s 失败 code=%s" % (sub2_id, r.get("code")))
        except Exception as e:
            print("  ⚠ Sub2 删 id=%s 异常 %s" % (sub2_id, str(e)[:60]))
print("✓ Sub2 删除 %d 个" % sub2_deleted)

# 5. 删本地子号行 + 母号行
n_sub = d.execute(text("delete from adobe_members where admin_id in "
                       "(4,5,8,9,11,12,14,16,17,19)")).rowcount
n_mom = d.execute(text("delete from adobe_accounts where id in "
                       "(4,5,8,9,11,12,14,16,17,19)")).rowcount
d.commit()
print("✓ 本地删除:成员行 %d(含子号+母号镜像) · 母号 %d" % (n_sub, n_mom))
print("=== 完成 ===")
