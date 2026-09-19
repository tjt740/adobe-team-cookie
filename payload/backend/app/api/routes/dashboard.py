"""运营驾驶舱聚合接口(只读概览 + 触发自愈 + 自愈活动流 + autopilot 旋钮读写 + 指标历史)。"""
import datetime
import subprocess

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db

router = APIRouter(prefix="/dashboard", tags=["驾驶舱"], dependencies=[Depends(get_current_user)])

AUTOPILOT_CONF = "/opt/adobeteam/autopilot.conf"
_KNOB_KEYS = ["MODE", "AUTO_SUB2_CLEAN", "AUTO_PULL", "AUTO_FILL_DEFICIT", "AUTO_ACTIVATE",
              "AUTO_LIVENESS", "AUTO_RELOGIN", "TARGET_PER_ADMIN", "PULL_CAP_PER_RUN",
              "CLEAN_CAP_PER_RUN", "BALANCE_FLOOR", "VALID_ADMIN_WARN", "ALERT_MODE"]
_SVC = {"selfheal": "adobeteam-selfheal.service", "autopilot": "adobeteam-autopilot.service",
        "pruneorg": "adobeteam-pruneorg.service"}

# 告警权重:一条 critical 直接把分数打到 66,warning 各扣 13,info 各扣 4
_ALERT_W = {"critical": 34, "warning": 13, "info": 4}


def _compute_health(admins: dict, capacity: dict, emails: dict, sub2: dict) -> dict:
    """从各聚合指标推导系统健康分 + 主动告警清单(前端红铃铛/健康分用)。"""
    alerts = []
    if sub2.get("enabled") and (sub2.get("ok") is False or sub2.get("error")):
        alerts.append(("critical", "Sub2 网关不可达",
                       (sub2.get("message") or sub2.get("error") or "无法连接销售网关")[:80]))
    unused = emails.get("unused", 0)
    if unused == 0:
        alerts.append(("critical", "邮箱池已空", "无可用邮箱,建号会全部失败,尽快换血导入"))
    elif unused < 200:
        alerts.append(("warning", "邮箱池偏低", "仅剩 %d 个可用邮箱,建议补充" % unused))
    deficit = capacity.get("deficit", 0)
    if deficit >= 30:
        alerts.append(("warning", "子号缺口偏大", "缺 %d 个满 4000 子号,自愈补号中" % deficit))
    pending = sub2.get("pending")
    if isinstance(pending, int) and pending >= 20:
        alerts.append(("warning", "待推堆积", "%d 个待推,持续未消化可能是分叉号或推送异常" % pending))
    dead = admins.get("dead_org", 0)
    if dead >= 5:
        alerts.append(("warning", "死母号堆积", "%d 个组织已删母号,建议一键清死母号" % dead))
    unchecked = admins.get("unchecked", 0)
    if unchecked >= 10:
        alerts.append(("info", "母号待检测", "%d 个母号未测活" % unchecked))
    total = admins.get("total", 0) or 1
    valid = admins.get("valid", 0)
    if valid / total < 0.7:
        alerts.append(("warning", "有效母号占比低", "仅 %d/%d 有效" % (valid, total)))
    score = max(0, min(100, 100 - sum(_ALERT_W.get(lv, 5) for lv, *_ in alerts)))
    grade = "优秀" if score >= 90 else "良好" if score >= 75 else "注意" if score >= 60 else "告警"
    return {"score": score, "grade": grade,
            "alerts": [{"level": lv, "title": t, "detail": d} for lv, t, d in alerts]}


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    return _gather(db)


def _gather(db: Session) -> dict:
    ex = lambda q: db.execute(text(q)).scalar()  # noqa: E731
    total_admin = ex("select count(*) from adobe_accounts")
    valid = ex("select count(*) from adobe_accounts where is_valid=1")
    unchecked = ex("select count(*) from adobe_accounts where is_valid is null")
    type2e = ex("select count(*) from adobe_accounts where coalesce(is_valid,0)<>1 "
                "and (lower(check_message) like '%type2e%' or lower(check_message) like '%eoachoose%')")
    dead_org = ex("select count(*) from adobe_accounts where coalesce(is_valid,0)=0 "
                  "and not (lower(check_message) like '%type2e%' or lower(check_message) like '%eoachoose%')")
    reg = ex("select count(*) from adobe_members where is_admin=0 and registered=1")
    full = ex("select count(*) from adobe_members where is_admin=0 and registered=1 "
              "and abs(coalesce(credits,0)-4000)<0.001")
    zero = ex("select count(*) from adobe_members where is_admin=0 and registered=1 and coalesce(credits,0)=0")
    cookie = ex("select count(*) from adobe_members where is_admin=0 and registered=1 and cookie<>''")
    building = max(0, (reg or 0) - (full or 0) - (zero or 0))
    rows = db.execute(text(
        "select count(m.id) filter(where m.is_admin=0 and m.registered=1 and "
        "abs(coalesce(m.credits,0)-4000)<0.001) fc from adobe_accounts a "
        "left join adobe_members m on m.admin_id=a.id where a.is_valid=1 group by a.id")).fetchall()
    healthy = sum(r[0] for r in rows)
    deficit = sum(max(0, 9 - r[0]) for r in rows)
    ceiling = len(rows) * 9
    em = dict(db.execute(text("select is_used, count(*) from emails group by is_used")).fetchall())
    sub2 = {"enabled": False}
    try:
        from app.api.routes.sub2 import _get_config, _existing_keys, _candidates
        cfg = _get_config(db)
        sub2["enabled"] = bool(cfg.get("enabled"))
        sub2["concurrency"] = cfg.get("concurrency")
        if cfg.get("enabled") and cfg.get("base_url") and cfg.get("admin_token"):
            exi = _existing_keys(cfg)
            if exi.get("ok"):
                cand, _in = _candidates(db, exi, None, platform=cfg.get("platform"))
                sub2.update(ok=True, live=exi.get("count"), pending=len(cand))
            else:
                sub2.update(ok=False, message=exi.get("message"))
    except Exception as e:  # noqa: BLE001
        sub2["error"] = str(e)[:120]
    admins_d = {"total": total_admin, "valid": valid, "type2e": type2e,
                "dead_org": dead_org, "unchecked": unchecked}
    capacity_d = {"healthy": healthy, "target": ceiling, "deficit": deficit, "ceiling": ceiling}
    emails_d = {"unused": em.get(0, 0), "used": em.get(1, 0), "total": sum(em.values())}
    return {
        "admins": admins_d,
        "members": {"registered": reg, "full4000": full, "building": building, "zero": zero, "cookie": cookie},
        "capacity": capacity_d,
        "emails": emails_d,
        "sub2": sub2,
        "health": _compute_health(admins_d, capacity_d, emails_d, sub2),
    }


# —— 指标历史(迷你趋势图):独立表,由 adobeteam-snapshot.timer 每 15 分钟写一行 ——
_HISTORY_DDL = (
    "create table if not exists metric_history ("
    " id integer primary key autoincrement, ts text not null,"
    " valid integer, full4000 integer, sub2_live integer,"
    " emails_unused integer, deficit integer, score integer)"
)
_HIST_KEYS = ["valid", "full4000", "sub2_live", "emails_unused", "deficit", "score"]


def snapshot_metrics(db: Session) -> dict:
    """采集一次核心指标写入 metric_history(供快照 timer 调用)。"""
    db.execute(text(_HISTORY_DDL))
    g = _gather(db)
    row = {
        "ts": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "valid": g["admins"]["valid"], "full4000": g["members"]["full4000"],
        "sub2_live": g["sub2"].get("live"), "emails_unused": g["emails"]["unused"],
        "deficit": g["capacity"]["deficit"], "score": (g.get("health") or {}).get("score"),
    }
    db.execute(text(
        "insert into metric_history (ts,valid,full4000,sub2_live,emails_unused,deficit,score)"
        " values (:ts,:valid,:full4000,:sub2_live,:emails_unused,:deficit,:score)"), row)
    # 只保留最近 ~30 天(15min×2880 行)防止无限增长
    db.execute(text("delete from metric_history where id < "
                    "(select max(id) from metric_history) - 3000"))
    db.commit()
    return row


@router.get("/history")
def history(points: int = 96, db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text(_HISTORY_DDL))
        db.commit()
        n = max(2, min(500, points))
        rows = db.execute(text(
            "select ts,valid,full4000,sub2_live,emails_unused,deficit,score"
            " from metric_history order by id desc limit :n"), {"n": n}).fetchall()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)[:120], "ts": [], "series": {}}
    rows = rows[::-1]
    series = {k: [r[i + 1] for r in rows] for i, k in enumerate(_HIST_KEYS)}
    return {"ok": True, "ts": [r[0] for r in rows], "series": series, "count": len(rows)}


@router.get("/search")
def search(q: str = "", db: Session = Depends(get_db)) -> dict:
    """全局搜索(Ctrl+K):按邮箱/ID/组织在母号、子号、邮箱池里找。"""
    q = (q or "").strip()
    if len(q) < 2:
        return {"ok": True, "q": q, "results": []}
    stripped = q.replace("%", "").replace("_", "")
    if not stripped:  # 纯通配符查询,剥离后为空 → 不做 match-all
        return {"ok": True, "q": q, "results": []}
    like = "%" + stripped + "%"
    p = {"k": like, "e": q}
    out = []
    for r in db.execute(text(
        "select id,email,is_valid,org_id from adobe_accounts"
        " where email like :k or cast(id as text)=:e or org_id like :k limit 8"), p).fetchall():
        out.append({"type": "admin", "id": r[0], "email": r[1] or "",
                    "status": "有效" if r[2] == 1 else ("未测" if r[2] is None else "无效"),
                    "extra": (r[3] or "")[:24]})
    for r in db.execute(text(
        "select id,email,admin_id,credits,registered from adobe_members"
        " where is_admin=0 and (email like :k or cast(id as text)=:e) limit 8"), p).fetchall():
        out.append({"type": "member", "id": r[0], "email": r[1] or "",
                    "status": ("%d 分" % int(r[3] or 0)) if r[4] else "建号中",
                    "extra": "母号#%s" % r[2]})
    for r in db.execute(text(
        "select id,email,is_used from emails"
        " where email like :k or cast(id as text)=:e limit 8"), p).fetchall():
        out.append({"type": "email", "id": r[0], "email": r[1] or "",
                    "status": "已用" if r[2] else "未用", "extra": ""})
    return {"ok": True, "q": q, "results": out[:24]}


@router.post("/email-spotcheck")
def email_spotcheck(n: int = 6, db: Session = Depends(get_db)) -> dict:
    """随机抽 N 个未用邮箱实测能否收码,报成功率(主动发现邮箱批次静默失效)。"""
    import concurrent.futures as cf

    from app.services import mail_test  # noqa: PLC0415

    n = max(1, min(12, n))
    rows = db.execute(text(
        "select id,email,refresh_token,client_id from emails"
        " where is_used=0 and refresh_token is not null and refresh_token<>''"
        " and client_id is not null and client_id<>'' order by random() limit :n"),
        {"n": n}).fetchall()
    if not rows:
        return {"ok": True, "tested": 0, "passed": 0, "failed": 0, "rate": None,
                "samples": [], "message": "无可测邮箱(缺 refresh_token / client_id)"}

    def probe(r):
        try:
            rr = mail_test.test_receive_email(email_addr=r[1], refresh_token=r[2],
                                              client_id=r[3], proxy_url="", timeout=20)
            nrt = getattr(rr, "new_refresh_token", None)
            return {"id": r[0], "email": r[1], "success": bool(rr.success),
                    "message": (getattr(rr, "message", "") or "")[:120],
                    "new_rt": nrt if (nrt and nrt != r[2]) else None}
        except Exception as e:  # noqa: BLE001
            return {"id": r[0], "email": r[1], "success": False,
                    "message": str(e)[:120], "new_rt": None}

    with cf.ThreadPoolExecutor(max_workers=min(len(rows), 6)) as ex:
        raw = list(ex.map(probe, rows))
    # 微软 refresh_token 一次性轮换:兑换后必须把新令牌存回,否则旧 token 作废=烧号
    for x in raw:
        if x.get("new_rt"):
            db.execute(text("update emails set refresh_token=:rt where id=:id"),
                       {"rt": x["new_rt"], "id": x["id"]})
    db.commit()
    passed = sum(1 for x in raw if x["success"])
    samples = [{"email": x["email"], "success": x["success"], "message": x["message"]} for x in raw]
    return {"ok": True, "tested": len(samples), "passed": passed,
            "failed": len(samples) - passed, "rate": round(passed / len(samples) * 100),
            "samples": samples}


@router.post("/trigger/{action}")
def trigger(action: str) -> dict:
    svc = _SVC.get(action)
    if not svc:
        return {"ok": False, "message": "未知操作"}
    label = {"selfheal": "自愈", "autopilot": "巡航", "pruneorg": "清死母号"}.get(action, action)
    try:
        subprocess.run(["systemctl", "start", "--no-block", svc], check=True, timeout=10)
        return {"ok": True, "message": "已触发" + label}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)[:140]}


@router.get("/activity")
def activity() -> dict:
    try:
        out = subprocess.run(
            ["journalctl", "-u", "adobeteam-selfheal.service", "-n", "120", "--no-pager", "-o", "cat"],
            capture_output=True, text=True, timeout=15).stdout
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)[:140], "runs": []}
    runs, cur = [], None
    for line in out.splitlines():
        line = line.strip()
        if "号池自愈(10m)" in line:
            if cur:
                runs.append(cur)
            cur = {"overview": line, "actions": []}
        elif cur is not None and any(m in line for m in ("🧹", "自动推送", "自动补号", "激活新母号")):
            cur["actions"].append(line)
    if cur:
        runs.append(cur)
    return {"ok": True, "runs": runs[-8:][::-1]}


@router.get("/autopilot-config")
def get_autopilot_config() -> dict:
    conf = {}
    try:
        for line in open(AUTOPILOT_CONF, encoding="utf-8"):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                conf[k.strip()] = v.strip()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)[:140]}
    return {"ok": True, "config": {k: conf.get(k, "") for k in _KNOB_KEYS}}


class KnobIn(BaseModel):
    key: str
    value: str


@router.put("/autopilot-config")
def put_autopilot_config(body: KnobIn) -> dict:
    if body.key not in _KNOB_KEYS:
        return {"ok": False, "message": "不允许修改此项"}
    val = str(body.value).strip().replace("\n", "")
    try:
        lines, found = [], False
        for line in open(AUTOPILOT_CONF, encoding="utf-8"):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s and s.split("=", 1)[0].strip() == body.key:
                lines.append("%s=%s\n" % (body.key, val)); found = True
            else:
                lines.append(line if line.endswith("\n") else line + "\n")
        if not found:
            lines.append("%s=%s\n" % (body.key, val))
        open(AUTOPILOT_CONF, "w", encoding="utf-8").writelines(lines)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)[:140]}
    return {"ok": True, "key": body.key, "value": val}
