#!/usr/bin/env python3
"""AdobeTeam 号池自动巡航 (autopilot).

模式:
  dry-run : 只巡查、算出计划、推送报告,不动手(默认,安全)
  active  : 在 dry-run 基础上执行安全动作——
            · 自动把号池新可用子号推进 Sub2(需 Sub2 启用+巡航自动推送+已配分组)
            · (可选,默认关)AUTO_RELOGIN=true 时自动重登过期母号(保活 token)
            注:自动"拉号"(消耗邮箱/账号,需盯着)默认不做,仍在母号管理页手动触发。

配置从 /opt/adobeteam/autopilot.conf 读取(简单 KEY=VALUE)。安静时段内不推 Bark、不执行 active 动作。
"""
import sys, os, sqlite3, datetime, json, urllib.parse, urllib.request

try:
    import fcntl  # 单实例锁:selfheal 与 4h 巡航不并发进入拉号段
except ImportError:  # noqa: BLE001
    fcntl = None

BACKEND = "/opt/adobeteam/backend"
sys.path.insert(0, BACKEND)
try:
    # app.* 用相对 sqlite:///app.db,切到 backend 目录确保始终指向正确库(不依赖 CWD)
    os.chdir(BACKEND)
except OSError:
    pass
DB = BACKEND + "/app.db"
CONF = "/opt/adobeteam/autopilot.conf"

DEFAULTS = {
    "MODE": "dry-run",
    "TARGET_PER_ADMIN": "9",
    "RELOGIN_AFTER_HOURS": "12",
    "PULL_CAP_PER_RUN": "30",
    "PUSH_CAP_PER_RUN": "50",       # active 时单轮最多自动推多少个新子号
    "RELOGIN_CAP_PER_RUN": "3",     # active + AUTO_RELOGIN 时单轮最多重登几个母号
    "AUTO_RELOGIN": "false",        # 是否自动重登过期母号(慢,默认关)
    "EMAIL_POOL_WARN": "100",
    "VALID_ADMIN_WARN": "18",         # 有效母号跌破此数→报告⚠+Bark提醒补母号
    "ALERT_MODE": "smart",          # Bark 推送分级:all=每轮都推 / smart=有异常或有动作才推 / off=从不推
    "AUTO_SUB2_CLEAN": "false",     # Sub2 余额<地板/残号 → 删Sub2+踢母号+删本地(默认关,先看 dry-run)
    "CLEAN_CAP_PER_RUN": "8",       # 每轮最多清几个坏号
    "BALANCE_FLOOR": "100",         # Sub2 余额低于此判为需删
    "AUTO_PULL": "false",           # 自愈清坏号后,1:1 精确补回被删的个数(mode=add,默认关)
    "AUTO_FILL_DEFICIT": "false",   # 每轮自动把有缺口的母号补到 TARGET_PER_ADMIN(默认关)
    "AUTO_LIVENESS": "false",        # 每轮真出图测活 N 个子号(先刷token,耗少量额度)
    "AUTO_LIVENESS_CLEAN": "false",  # 测活死号(刷token后仍出不了图)自动删+补
    "LIVENESS_PER_RUN": "3",         # 每轮测活几个子号(保守,防耗额度)
    "AUTO_PRUNE_ORPHANS": "false",   # 自愈时删掉母号已删的孤儿子号(非手动导入)(默认关,破坏性)
    "AUTO_ACTIVATE": "true",         # 自动登录激活新导入母号(有凭据但从未登录)→ 变 valid → 进补号队列
    "ACTIVATE_CAP_PER_RUN": "2",     # 每轮最多激活几个新母号(登录慢,走 OTP,限量)
    "ACTIVATE_PROXY_RETRY": "3",     # 激活登录:代理/网络瞬时失败时换下一个代理重试的最大次数
    "BACKEND_URL": "http://127.0.0.1:8000",
    "ADMIN_USER": "admin",
    "ADMIN_PASS": "CHANGE_ME",
    "BARK_URL": "",
    "QUIET_START": "",              # 例 "17"(UTC 17:00 起安静);北京+8
    "QUIET_END": "",                # 例 "1"(UTC 01:00 结束)
}

# ---- 多平台号池 ----
DEFAULT_PLATFORM = "adobe_gemini"
# 号池展示元信息:emoji + 简称(Bark 双池分块用)
PLATFORM_META = {
    "adobe_gemini": ("🍌", "Gemini"),
    "adobe_gpt": ("🤖", "GPT"),
}


def platform_meta(p):
    return PLATFORM_META.get(p, ("📦", p))


def platforms_in_db():
    """当前需自愈的平台集合(至少含主平台 adobe_gemini;其余来自有效母号 platform 列)。
    platform 列未迁移时退回单平台,不炸。"""
    plats = {DEFAULT_PLATFORM}
    try:
        c = sqlite3.connect(DB)
        try:
            for (p,) in c.execute(
                "select distinct coalesce(platform,'adobe_gemini') from adobe_accounts"
            ).fetchall():
                if p:
                    plats.add(p)
        except sqlite3.OperationalError:
            pass
        c.close()
    except Exception:  # noqa: BLE001
        pass
    return sorted(plats)


def load_conf():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONF):
        for line in open(CONF, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def in_quiet(cfg):
    s, e = cfg.get("QUIET_START", "").strip(), cfg.get("QUIET_END", "").strip()
    if not s or not e:
        return False
    try:
        s, e = int(s), int(e)
    except ValueError:
        return False
    h = datetime.datetime.utcnow().hour
    return (s <= h < e) if s < e else (h >= s or h < e)  # 支持跨零点


def hours_since(ts):
    # last_login_at 由后端以 UTC(datetime.now(timezone.utc))写入,此处按 UTC 相减。
    if not ts:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(ts, fmt)
            return (datetime.datetime.utcnow() - dt).total_seconds() / 3600.0
        except ValueError:
            continue
    return None


def plan(cfg, platform=None):
    """算各有效母号的子号缺口。platform 指定时只统计该平台的母号(缺口/补号按平台独立)。"""
    target = int(cfg["TARGET_PER_ADMIN"])
    relogin_h = float(cfg["RELOGIN_AFTER_HOURS"])
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    if platform:
        admins = c.execute(
            "select id,email,is_valid,last_login_at from adobe_accounts "
            "where is_valid=1 and coalesce(platform,'adobe_gemini')=? order by id", (platform,)
        ).fetchall()
    else:
        admins = c.execute(
            "select id,email,is_valid,last_login_at from adobe_accounts where is_valid=1 order by id"
        ).fetchall()
    rows = []
    for a in admins:
        usable = c.execute(
            "select count(*) from adobe_members where admin_id=? and is_admin=0 "
            "and registered=1 and abs(coalesce(credits,0)-4000)<0.001", (a["id"],)
        ).fetchone()[0]
        deficit = max(0, target - usable)
        age = hours_since(a["last_login_at"])
        stale = (age is None) or (age > relogin_h)
        rows.append({"id": a["id"], "email": a["email"], "usable": usable,
                     "deficit": deficit, "age": age, "stale": stale})
    invalid_n = c.execute("select count(*) from adobe_accounts where coalesce(is_valid,0)=0").fetchone()[0]
    email_unused = c.execute("select count(*) from emails where is_used=0").fetchone()[0]
    c.close()
    return rows, invalid_n, email_unused, target


def format_deficit_detail(rows, target, top=8):
    """某平台缺口明细行:#母号 usable/target 缺N ⚠重登。供 4h 巡航展开(自愈保持紧凑不展开)。"""
    short = sorted([r for r in rows if r["deficit"] > 0], key=lambda r: -r["deficit"])
    if not short:
        return []
    out = []
    for r in short[:top]:
        tag = ("  ⚠重登" + (f"({int(r['age'])}h)" if r["age"] is not None else "(从未)")) if r["stale"] else ""
        out.append(f"    #{r['id']} {r['usable']}/{target} 缺{r['deficit']}{tag}")
    if len(short) > top:
        out.append(f"    …另有 {len(short)-top} 个母号有缺口")
    return out


def sub2_status(platform=None):
    """只读汇报某平台 Sub2。返回 (报告文本 or None, gateway_ok: True/False/None, 待推数)。
    gateway_ok=None 表示未启用/未配置(不参与告警定级);False 表示网关不可达(crit)。"""
    try:
        from app.db.session import SessionLocal
        from app.api.routes.sub2 import _get_config, _existing_keys, _candidates
        db = SessionLocal()
        try:
            cfg = _get_config(db, platform)
            if not cfg.get("enabled"):
                return None, None, 0
            if not cfg.get("base_url") or not cfg.get("admin_token"):
                return "Sub2: 未配置完整,跳过", None, 0
            existing = _existing_keys(cfg)
            if not existing.get("ok"):
                return f"⚠ Sub2 网关不可达/令牌失效:{existing.get('message', '未知')}", False, 0
            rows, in_sub2 = _candidates(db, existing, None, platform=cfg.get("platform"))
            text = (f"Sub2: 待推新子号 {len(rows)} · 已在库 {in_sub2} · 该平台库存 {existing.get('count', 0)}"
                    + (" · 自动推送开" if cfg.get("auto_push") else " · 自动推送关"))
            return text, True, len(rows)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        return f"⚠ Sub2 状态获取失败:{e}", False, 0


def act_push_sub2(cfg, platform=None):
    """active:把号池新可用子号自动推进 Sub2(需 enabled+auto_push+分组+网关可达)。
    platform 指定时只推该平台的子号(其母号 platform 归属)到该平台分组。"""
    try:
        from app.db.session import SessionLocal
        from app.api.routes.sub2 import _get_config, _existing_keys, _candidates, _member_item, mark_pushed
        from app.services import sub2_client
        db = SessionLocal()
        try:
            c = _get_config(db, platform)
            if not (c.get("enabled") and c.get("auto_push")):
                return None
            if not c.get("group_ids"):
                return "⚠ 自动推送:未配置分组,跳过"
            existing = _existing_keys(c)
            if not existing.get("ok"):
                return f"⚠ 自动推送:网关不可达,已中止({existing.get('message', '')})"
            rows, _ = _candidates(db, existing, int(cfg["PUSH_CAP_PER_RUN"]), platform=c.get("platform"))
            if not rows:
                return "自动推送:无新号"
            items = [_member_item(m) for m in rows]
            # 小批推(默认协议铸 18 个 token slot 较慢,50 个一把会超时→显示"创建None")
            chunk_n = int(cfg.get("PUSH_CHUNK", "12"))
            created = updated = failed = skipped = 0
            for i in range(0, len(items), chunk_n):
                chunk = items[i:i + chunk_n]
                try:
                    resp = sub2_client.import_tokens({**c, "concurrency": c.get("concurrency", 10)}, chunk)
                except Exception:  # noqa: BLE001
                    failed += len(chunk); continue
                res = resp.get("result") if isinstance(resp.get("result"), dict) else {}
                created += int(res.get("created") or 0)
                updated += int(res.get("updated") or 0)   # 已在库→刷新,也是成功
                failed += int(res.get("failed") or 0)
                skipped += int(res.get("skipped") or 0)
                mark_pushed(db, rows[i:i + chunk_n], res)  # 打标已入库,兜底 Sub2 分叉漏配
            done = created + updated
            return (f"✅ 自动推送 {len(rows)} 个:成功 {done}(新建{created}/更新{updated})"
                    f" · 失败 {failed}" + (f" · 跳过 {skipped}" if skipped else ""))
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        return f"⚠ 自动推送异常:{e}"


def act_activate_new_admins(cfg):
    """自动激活新导入母号:有凭据(refresh_token+client_id)但从未登录成功(is_valid≠True)、
    且非永久失败(type2e/无组织)的母号,自动登录获取管理权限。成功→is_valid=True→下一轮进补号队列。
    限量(登录慢,走 OTP)。永久失败的靠 check_message 排除,失败的靠 last_login_at 节流(不每轮重试)。"""
    if cfg.get("AUTO_ACTIVATE", "true").lower() != "true":
        return None
    cap = max(1, int(cfg.get("ACTIVATE_CAP_PER_RUN", "2")))
    try:
        from sqlalchemy import select
        from app.db.session import SessionLocal
        from app.models.adobe_account import AdobeAccount
        from app.services import adobe_admin, proxy_pool
        from app.crud import setting as setting_crud
    except Exception as e:  # noqa: BLE001
        return f"⚠ 激活新母号初始化失败:{e}"
    perm_fail = ("type2e", "eoachoose", "无可用组织", "无可用产品", "无组织", "选择账号资料")
    db = SessionLocal()
    try:
        cands = db.scalars(
            select(AdobeAccount).where(
                AdobeAccount.is_valid.isnot(True),
                AdobeAccount.refresh_token != "",
                AdobeAccount.client_id != "",
            ).order_by(AdobeAccount.last_login_at.asc(), AdobeAccount.id)  # 从未登录的(null)排最前
        ).all()
        targets = [a for a in cands
                   if not any(m in (a.check_message or "").lower() for m in perm_fail)][:cap]
        if not targets:
            return None
        settings = setting_crud.get_settings(db)
        proxy_raw = (settings.proxy_url if (settings.proxy_enabled and (settings.proxy_url or "").strip()) else "")
        retry_n = max(1, int(cfg.get("ACTIVATE_PROXY_RETRY", "3")))

        def _login_rot(a):  # 代理轮换:代理/网络瞬时错换下一个代理重试;非瞬时错直接抛
            last = None
            for _ in range(retry_n):
                try:
                    return adobe_admin.login_account(
                        email=a.email, adobe_password=a.adobe_password,
                        refresh_token=a.refresh_token, client_id=a.client_id,
                        proxy_url=proxy_pool.next_proxy(proxy_raw), otp_timeout=120)
                except Exception as e:  # noqa: BLE001
                    last = e
                    if not any(t.lower() in str(e).lower() for t in _ACTIVATE_TRANSIENT):
                        raise
            raise last
        ok, bad, done = 0, 0, []
        for acc in targets:
            try:
                res = _login_rot(acc)
                rotated = res.get("rotated_refresh_token") or ""
                if rotated:
                    acc.refresh_token = rotated
                acc.admin_token = res.get("token") or ""
                acc.org_id = res.get("org_id") or ""
                acc.product_id = res.get("product_id") or ""
                acc.license_group_id = res.get("license_group_id") or ""
                acc.has_org = bool(res.get("has_org"))
                acc.is_valid = bool(res.get("has_org"))
                acc.last_login_at = datetime.datetime.now(datetime.timezone.utc)  # 节流:失败的也不每轮重试
                if not res.get("has_org"):
                    acc.check_message = (res.get("message") or "登录成功但无可用组织/产品")[:500]
                db.commit()
                if res.get("has_org"):
                    ok += 1; done.append(acc.id)
                else:
                    bad += 1
            except Exception as e:  # noqa: BLE001
                acc.check_message = str(e)[:500]
                acc.last_login_at = datetime.datetime.now(datetime.timezone.utc)
                db.commit()
                bad += 1
        return f"🆕 激活新母号:成功 {ok} {done or ''} · 失败/无组织 {bad}(共试 {len(targets)})"
    finally:
        db.close()


def act_relogin(cfg, stale):
    """active + AUTO_RELOGIN:自动重登过期母号(慢,限量)。"""
    if cfg.get("AUTO_RELOGIN", "false").lower() != "true" or not stale:
        return None
    cap = int(cfg["RELOGIN_CAP_PER_RUN"])
    targets = stale[:cap]
    try:
        from sqlalchemy import select
        from app.db.session import SessionLocal
        from app.models.adobe_account import AdobeAccount
        from app.services import adobe_admin, proxy_pool
        from app.crud import setting as setting_crud
    except Exception as e:  # noqa: BLE001
        return f"⚠ 自动重登初始化失败:{e}"
    ok, bad = 0, 0
    for r in targets:
        db = SessionLocal()
        try:
            acc = db.scalar(select(AdobeAccount).where(AdobeAccount.id == r["id"]))
            if acc is None:
                bad += 1
                continue
            settings = setting_crud.get_settings(db)
            proxy = proxy_pool.next_proxy(settings.proxy_url) if settings.proxy_enabled and settings.proxy_url.strip() else ""
            res = adobe_admin.login_account(
                email=acc.email, adobe_password=acc.adobe_password,
                refresh_token=acc.refresh_token, client_id=acc.client_id,
                proxy_url=proxy, otp_timeout=120,
            )
            rotated = res.get("rotated_refresh_token") or ""
            if rotated:
                acc.refresh_token = rotated
            acc.admin_token = res.get("token") or ""
            acc.org_id = res.get("org_id") or ""
            acc.product_id = res.get("product_id") or ""
            acc.license_group_id = res.get("license_group_id") or ""
            acc.has_org = bool(res.get("has_org"))
            acc.is_valid = bool(res.get("has_org"))
            acc.last_login_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
            ok += 1 if res.get("has_org") else 0
            bad += 0 if res.get("has_org") else 1
        except Exception:  # noqa: BLE001
            bad += 1
        finally:
            db.close()
    return f"🔁 自动重登 {len(targets)} 个母号:成功 {ok} · 失败/无组织 {bad}"


def act_health_clean(cfg, do_act, platform=None):
    """按余额自愈:Sub2 余额<地板 / 残号(上限10刷新后仍10)→ 删Sub2+踢母号+删本地行。
    do_act=False 只扫描报告(dry-run 影子)。platform 指定时只清该平台 Sub2 账号。
    返回 (报告文本 or None, 缺口 dict, 坏号数)。"""
    try:
        from app.db.session import SessionLocal
        from app.api.routes.sub2 import health_clean, HealthCleanIn
        floor = float(cfg.get("BALANCE_FLOOR", "100"))
        cap = int(cfg.get("CLEAN_CAP_PER_RUN", "8"))
        db = SessionLocal()
        try:
            # 判死靠 Sub2 自带的 temp_unschedulable_reason(真实请求失败记录),不需我们全量刷余额;
            # 关掉 refresh_first 大幅降低对 Sub2 网关的负载(避免自己把网关刷过载→Cloudflare 报错)。
            r = health_clean(HealthCleanIn(dry_run=not do_act, balance_floor=floor, cap=cap,
                                           refresh_first=False, platform=platform or ""), db)
        finally:
            db.close()
        if not r.get("ok"):
            return f"⚠ 余额自愈:{r.get('message', '失败')}", {}, 0
        bad, crip, dep = r.get("to_delete", 0), r.get("crippled", 0), r.get("depleted", 0)
        if do_act:
            txt = (f"🧹 余额自愈:已清 {r.get('cleaned', 0)}/{bad}(残{crip}+枯{dep})"
                   f" · 健康 {r.get('healthy', 0)} · 影响母号 {r.get('affected_admins', [])}")
        else:
            txt = (f"余额自愈(影子):会清 {bad}(残{crip}+枯{dep}) · 健康 {r.get('healthy', 0)}"
                   f" · 未知跳过 {r.get('unknown', 0)}")
        return txt, r.get("deficits", {}), bad
    except Exception as e:  # noqa: BLE001
        return f"⚠ 余额自愈异常:{e}", {}, 0


def _backend_login(cfg):
    """登录后端,返回 (base, token)。失败抛异常。"""
    base = cfg.get("BACKEND_URL", "http://127.0.0.1:8000")
    data = json.dumps({"username": cfg.get("ADMIN_USER", "admin"),
                       "password": cfg.get("ADMIN_PASS", "CHANGE_ME")}).encode()
    req = urllib.request.Request(base + "/api/auth/login", data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        tok = json.loads(r.read().decode())
    return base, (tok.get("token") or {}).get("access_token")


def _backend_call(base, path, token=None, body=None, method="GET", timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base + path, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


STALE_BUILD_SEC = 2400  # 看门狗:running build 超此秒数(40分)无完成→判僵死,不再阻塞补号


def _build_running(base, token):
    """是否已有 build 拉号任务在跑(避免叠加拉号,防重复消耗)。
    查询失败 fail-closed=True(本轮跳过拉号)——宁可这轮不拉,也不冒重复拉号双倍烧邮箱的险。
    limit=50 覆盖 JobManager 保留窗口,避免长跑 build 被更新任务挤出漏检。
    看门狗:running 但已超 STALE_BUILD_SEC 无完成的判僵死,不计为阻塞(否则一个卡死任务
    会永久堵死补号 → 池子只减不增萎缩,已踩过)。"""
    try:
        import time as _t
        jobs = _backend_call(base, "/api/adobe-accounts/jobs?limit=50", token)
        now = _t.time()
        for j in (jobs or []):
            if j.get("status") != "running" or not str(j.get("type", "")).startswith("build"):
                continue
            try:
                age = now - float(j.get("created_at") or now)
            except (TypeError, ValueError):
                age = 0
            if age > STALE_BUILD_SEC:
                print("\u26a0 \u50f5\u6b7b\u62c9\u53f7\u4efb\u52a1 job#%s(\u5df2 %d \u5206\u949f\u672a\u5b8c\u6210)\u2192 \u89c6\u4e3a\u975e\u963b\u585e" % (j.get("id"), int(age / 60)))
                continue
            return True
        return False
    except Exception:  # noqa: BLE001
        return True


def act_pull_refill(cfg, deficits):
    """AUTO_PULL:自愈清坏号后,对每个受影响母号 1:1 精确补回被删的个数(mode=add)。"""
    if cfg.get("AUTO_PULL", "false").lower() != "true":
        return None
    cap = int(cfg.get("PULL_CAP_PER_RUN", "30"))
    items = []
    for a, d in (deficits or {}).items():
        try:
            n = int(d)
        except (TypeError, ValueError):
            continue
        if n > 0:
            items.append((int(a), n))
    items.sort(key=lambda x: -x[1])
    groups, budget = {}, 0   # {每母号本轮补几个: [母号id,...]},受 PULL_CAP_PER_RUN 限总量
    for aid, n in items:
        take = min(n, cap - budget)
        if take <= 0:
            break
        groups.setdefault(take, []).append(aid)
        budget += take
    if not groups:
        return None
    try:
        base, token = _backend_login(cfg)
        if _build_running(base, token):
            return "🔧 1:1 补号:已有拉号任务在跑,本轮跳过"
        parts = []
        for n, ids in sorted(groups.items()):
            job = _backend_call(base, "/api/adobe-accounts/build-team-batch", token,
                                {"admin_ids": ids, "count": n, "mode": "add"}, "POST")
            parts.append(f"母号{ids}×{n}(job#{job.get('id')})")
        return "🔧 1:1 补号:" + " ".join(parts)
    except Exception as e:  # noqa: BLE001
        return f"⚠ 1:1 补号触发失败:{e}"


def act_fill_deficit(cfg, rows):
    """AUTO_FILL_DEFICIT:每轮把有缺口的母号补到 TARGET(mode=target),按 PULL_CAP_PER_RUN 限总量。"""
    if cfg.get("AUTO_FILL_DEFICIT", "false").lower() != "true":
        return None
    target = int(cfg["TARGET_PER_ADMIN"])
    cap = int(cfg.get("PULL_CAP_PER_RUN", "30"))
    short = sorted([r for r in rows if r["deficit"] > 0], key=lambda r: -r["deficit"])
    picked, budget = [], 0
    for r in short:
        if picked and budget + r["deficit"] > cap:
            continue   # 装箱式:跳过塞不下的大缺口,继续试更小的把 cap 用满
        picked.append(r["id"]); budget += r["deficit"]
    if not picked:
        return None
    try:
        base, token = _backend_login(cfg)
        if _build_running(base, token):
            return "🪴 自动补号:已有拉号任务在跑,本轮跳过"
        job = _backend_call(base, "/api/adobe-accounts/build-team-batch", token,
                            {"admin_ids": picked, "count": target, "mode": "target"}, "POST")
        return (f"🪴 自动补号:{len(picked)} 个母号补到 {target}"
                f"(约 {budget} 个,job#{job.get('id')})")
    except Exception as e:  # noqa: BLE001
        return f"⚠ 自动补号触发失败:{e}"


def act_refill_targets(cfg, admin_ids):
    """把指定母号一律补齐到 TARGET_PER_ADMIN(mode=target,一个 build 顺序处理)。
    _build_running 防叠加;拉到的新号下一轮 act_push_sub2 自动 cookie 推进 Sub2。"""
    admin_ids = sorted({int(a) for a in (admin_ids or [])})
    if not admin_ids:
        return None
    target = int(cfg["TARGET_PER_ADMIN"])
    try:
        base, token = _backend_login(cfg)
        if _build_running(base, token):
            return f"🔧 补齐到{target}:已有拉号任务在跑,本轮跳过(下轮继续)"
        job = _backend_call(base, "/api/adobe-accounts/build-team-batch", token,
                            {"admin_ids": admin_ids, "count": target, "mode": "target"},
                            "POST", timeout=120)
        return f"🔧 补齐到{target}:母号{admin_ids}(job#{job.get('id')},后台拉,拉完下轮推Sub2)"
    except Exception as e:  # noqa: BLE001
        return f"⚠ 补齐触发失败:{e}"


LIVENESS_STATE = "/opt/adobeteam/.autopilot_liveness.json"


def act_liveness(cfg):
    """AUTO_LIVENESS:每轮真出图测活 N 个子号(后端先刷 token 再出图),
    死号(刷新后仍出不了图且明确失败)删+补(需 AUTO_LIVENESS_CLEAN)。
    子号按 id round-robin,游标存 LIVENESS_STATE。返回 (报告文本 or None, 缺口 dict)。"""
    if cfg.get("AUTO_LIVENESS", "false").lower() != "true":
        return None, {}
    n = max(1, int(cfg.get("LIVENESS_PER_RUN", "3")))
    cur = 0
    try:
        if os.path.exists(LIVENESS_STATE):
            cur = int((json.load(open(LIVENESS_STATE, encoding="utf-8")) or {}).get("cursor", 0))
    except Exception:  # noqa: BLE001
        cur = 0
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    # 只测有 device_token 的子号(免验证码快刷,刷新可靠;避免整登 429 导致误判)
    base_q = ("select id from adobe_members where is_admin=0 and registered=1 "
              "and access_token<>'' and coalesce(device_token,'')<>'' ")
    rows = c.execute(base_q + "and id>? order by id limit ?", (cur, n)).fetchall()
    if len(rows) < n:  # 环绕从头补
        rest = c.execute(base_q + "and id<=? order by id limit ?",
                         (cur, n - len(rows))).fetchall()
        rows = list(rows) + list(rest)
    c.close()
    ids = [r["id"] for r in rows]
    if not ids:
        return "测活:无可测子号", {}
    try:
        json.dump({"cursor": ids[-1]}, open(LIVENESS_STATE, "w", encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    do_clean = cfg.get("AUTO_LIVENESS_CLEAN", "false").lower() == "true"
    try:
        base, token = _backend_login(cfg)
        r = _backend_call(base, "/api/sub2/liveness-clean", token,
                          {"member_ids": ids, "dry_run": not do_clean, "cap": len(ids)},
                          "POST", timeout=max(180, 90 * len(ids)))
    except Exception as e:  # noqa: BLE001
        return f"⚠ 测活失败:{e}", {}
    if not r.get("ok"):
        return f"⚠ 测活:{r.get('message', '失败')}", {}
    tag = "🩺 测活" if do_clean else "测活(影子)"
    txt = (f"{tag}:测 {r.get('tested', 0)} · 活 {r.get('alive', 0)} · 死 {r.get('dead', 0)}"
           + (f"(已删 {r.get('cleaned', 0)})" if do_clean else "(不删)")
           + f" · 存疑 {r.get('inconclusive', 0)} · 刷token {r.get('refreshed', 0)}")
    return txt, (r.get("deficits", {}) if do_clean else {})


def compute_alert(cfg, rows, invalid_n, email_unused, gateway_ok, sub2_pending):
    """按信号定级并给出原因。level: crit(需立即处理)/ warn(有缺口或待办)/ info(健康)。"""
    warn_thr = int(cfg["EMAIL_POOL_WARN"])
    tot_deficit = sum(r["deficit"] for r in rows)
    stale_n = sum(1 for r in rows if r["stale"])
    reasons, level = [], "info"
    if gateway_ok is False:
        level = "crit"; reasons.append("Sub2 网关不可达/令牌失效")
    if email_unused < warn_thr:
        level = "crit"; reasons.append(f"邮箱池偏低 {email_unused}")
    if level != "crit":
        if tot_deficit > 0:
            level = "warn"; reasons.append(f"号池缺口 {tot_deficit}")
        if stale_n > 0:
            level = "warn"; reasons.append(f"{stale_n} 个母号待重登")
        if invalid_n > 0:
            level = "warn"; reasons.append(f"{invalid_n} 个无效母号")
        if sub2_pending > 0:
            level = "warn"; reasons.append(f"Sub2 待推 {sub2_pending}")
    return level, reasons


def should_alert(cfg, level, has_actions):
    """smart:有异常(warn/crit)或本轮执行过动作才推;all:每轮都推;off:从不推。"""
    mode = cfg.get("ALERT_MODE", "smart").strip().lower()
    if mode == "off":
        return False
    if mode == "all":
        return True
    return bool(has_actions) or level in ("warn", "crit")


def push_bark(cfg, body, title, should_push):
    url = cfg.get("BARK_URL", "").strip()
    if not url:
        return "(未配置 BARK_URL,跳过推送)"
    if in_quiet(cfg):
        return "(安静时段,不推 Bark)"
    if not should_push:
        return "(smart:本轮无异常/无动作,静默不推)"
    data = urllib.parse.urlencode({
        "title": title, "body": body, "group": "adobeteam", "sound": "default",
    }).encode("utf-8")
    last = ""
    for attempt in range(2):
        try:
            req = urllib.request.Request(url.rstrip("/"), data=data, method="POST")
            with urllib.request.urlopen(req, timeout=15) as r:
                if 200 <= r.status < 300:
                    return f"(Bark 推送成功 HTTP {r.status})"
                last = f"HTTP {r.status}"
        except Exception as e:  # noqa: BLE001
            last = str(e)[:80]
    return f"⚠ Bark 推送失败:{last}"


_ACTIVATE_TRANSIENT = ("超时", "timeout", "timed out", "curl", "reset",
                       "WRONG_VERSION", "proxy", "网关", "未取到", "Connection")


def act_prune_orphans(cfg):
    """删掉母号已不存在的孤儿子号(admin_id 不在现有母号里、且非手动导入 is_imported)——
    这些号母号/组织已删,不该再被当候选反复推 Sub2 或被检测。手动导入的子号不动。
    需 AUTO_PRUNE_ORPHANS=true 才真删(默认关,破坏性 DB 操作)。"""
    if cfg.get("AUTO_PRUNE_ORPHANS", "false").lower() != "true":
        return None
    try:
        c = sqlite3.connect(DB)
        cur = c.execute(
            "delete from adobe_members where admin_id not in (select id from adobe_accounts) "
            "and coalesce(is_imported,0)=0"
        )
        n = cur.rowcount
        c.commit()
        c.close()
        return f"🧽 清孤儿子号 {n}(母号已删)" if n else None
    except Exception as e:  # noqa: BLE001
        return f"⚠ 清孤儿异常:{e}"


def platform_snapshot(cfg, platform):
    """该平台号池概况(纯 sqlite,无网关调用):rows + 健康/目标/缺口/母号数。"""
    rows, _iv, _eu, _tg = plan(cfg, platform=platform)
    return {
        "rows": rows,
        "healthy": sum(r["usable"] for r in rows),
        "target": len(rows) * int(cfg["TARGET_PER_ADMIN"]),
        "deficit": sum(r["deficit"] for r in rows),
        "admins": len(rows),
    }


def run_selfheal(cfg):
    """10 分钟定时器(逐平台自愈):每平台 推已就绪新号 → 探余额清坏号 → 缺口母号补到 TARGET。
    清孤儿 + 激活新母号为全局动作(平台无关)。Bark 双池分块,仅有坏号/失败才推(不刷屏)。"""
    if in_quiet(cfg):
        print("🩹 号池自愈(10m):安静时段,跳过")
        return
    active = (cfg["MODE"] == "active")
    do_clean = active and cfg.get("AUTO_SUB2_CLEAN", "false").lower() == "true"
    plats = platforms_in_db()

    # 全局动作(不分平台):清母号已删的孤儿子号
    global_acts = []
    orph = act_prune_orphans(cfg)
    if orph:
        global_acts.append(orph)

    blocks, any_bad = [], 0
    tot_healthy = tot_target = tot_deficit = 0
    for p in plats:
        emoji, label = platform_meta(p)
        acts = []
        if active:
            pu = act_push_sub2(cfg, platform=p)                 # 推已就绪新号(cookie/默认协议)
            if pu and "无新号" not in pu:
                acts.append(pu)
        hc_txt, deficits, sub2_bad = act_health_clean(cfg, do_clean, platform=p)  # 探余额 + 清坏号
        any_bad += sub2_bad
        snap = platform_snapshot(cfg, p)                        # 清坏号后重算缺口,fill 补到位
        tot_healthy += snap["healthy"]; tot_target += snap["target"]; tot_deficit += snap["deficit"]
        if active:
            fill = act_fill_deficit(cfg, snap["rows"])          # 缺口母号补到 TARGET(该平台)
            if fill:
                acts.append(fill)
        head = f"{emoji}{label} 健康{snap['healthy']}/{snap['target']} 缺{snap['deficit']}"
        lines = [head, "  " + (hc_txt or "(无自愈)")]
        lines += ["  " + a for a in acts]
        blocks.append("\n".join(lines))

    # 全局:激活新导入母号(登录即可,平台无关;放最后,慢,成功的下轮进各自平台补号队列)
    if active:
        act = act_activate_new_admins(cfg)
        if act:
            global_acts.append(act)

    overview = (f"🩹 号池自愈(10m) · {len(plats)}池 · 健康 {tot_healthy}/{tot_target}"
                f" · 缺口 {tot_deficit}")
    report = overview + "\n" + "\n".join(blocks)
    if global_acts:
        report += "\n— 全局 —\n" + " ".join(global_acts)
    try:
        _cw = sqlite3.connect(DB)
        _va = _cw.execute("select count(*) from adobe_accounts where is_valid=1").fetchone()[0]
        _cw.close()
    except Exception:  # noqa: BLE001
        _va = None
    _wa = int(cfg.get("VALID_ADMIN_WARN", "18"))
    if _va is not None and _va < _wa:
        report += "\n⚠ 有效母号偏低 %d(<%d),建议补母号(子号天花板=有效母号×9)" % (_va, _wa)
    print(report)
    # 有坏号清理、或任一动作失败(⚠)才推 Bark;避免刷屏。
    if (do_clean and any_bad > 0) or "⚠" in report:
        print(push_bark(cfg, report, "AdobeTeam 🩹 号池自愈", True))


def main():
    cfg = load_conf()
    # 单实例锁:selfheal 与 4h 巡航互斥,永不并发进入拉号段(防 TOCTOU 竞态双倍拉号)
    _lock_f = open("/opt/adobeteam/.autopilot.lock", "w")
    if fcntl is not None:
        try:
            fcntl.flock(_lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError):
            print("(另一巡航实例在跑,本轮跳过以防并发拉号)")
            return
    if (sys.argv[1].strip().lower() if len(sys.argv) > 1 else "") == "selfheal":
        run_selfheal(cfg)
        return
    quiet = in_quiet(cfg)
    active = (cfg["MODE"] == "active" and not quiet)
    do_clean = active and cfg.get("AUTO_SUB2_CLEAN", "false").lower() == "true"
    plats = platforms_in_db()

    # 全局态(母号重登/无效母号/邮箱池,跨平台共享)
    all_rows, invalid_n, email_unused, target = plan(cfg)   # 全平台母号
    stale = [r for r in all_rows if r["stale"]]

    # 逐平台:概况 + 推新号 + 清坏号 + 补缺口 + Sub2 待推
    blocks, actions, merged = [], [], {}
    tot_healthy = tot_target = tot_deficit = agg_pending = any_bad = 0
    gateway_ok = None
    for p in plats:
        emoji, label = platform_meta(p)
        acts = []
        if active:
            pu = act_push_sub2(cfg, platform=p)
            if pu and "无新号" not in pu:
                acts.append(pu)
        hc_txt, deficits, sub2_bad = act_health_clean(cfg, do_clean, platform=p)
        any_bad += sub2_bad
        if do_clean:
            for a, d in (deficits or {}).items():
                merged[a] = max(merged.get(a, 0), int(d))
        snap = platform_snapshot(cfg, p)
        tot_healthy += snap["healthy"]; tot_target += snap["target"]; tot_deficit += snap["deficit"]
        if active:
            fill = act_fill_deficit(cfg, snap["rows"])
            if fill:
                acts.append(fill)
        s2, gw, pending = sub2_status(platform=p)
        if gw is False:
            gateway_ok = False
        elif gw is True and gateway_ok is None:
            gateway_ok = True
        agg_pending += pending
        head = f"{emoji}{label} 健康{snap['healthy']}/{snap['target']} 缺{snap['deficit']} 待推{pending}"
        lines = [head, "  " + (hc_txt or "(无自愈)")]
        lines += ["  " + a for a in acts]
        lines += format_deficit_detail(snap["rows"], int(cfg["TARGET_PER_ADMIN"]))
        blocks.append("\n".join(lines))

    # 全局动作:重登过期母号 + 激活新母号 + 测活(平台无关)
    if active:
        rl = act_relogin(cfg, stale)
        if rl:
            actions.append(rl)
        actv = act_activate_new_admins(cfg)
        if actv:
            actions.append(actv)
        lv_txt, lv_deficits = act_liveness(cfg)
        if lv_txt:
            blocks.append("🩺 测活 " + lv_txt)
        for a, d in (lv_deficits or {}).items():
            merged[a] = max(merged.get(a, 0), int(d))
    # 汇总"真删"产生的缺口,统一 1:1 补号(母号已带 platform,补出的子号即对应平台)
    if merged:
        pr = act_pull_refill(cfg, merged)
        if pr:
            actions.append(pr)

    warn = int(cfg["EMAIL_POOL_WARN"])
    L = [f"🤖 AdobeTeam 巡航 · {cfg['MODE']}" + ("(安静时段)" if quiet else "")]
    L.append(f"号池 健康 {tot_healthy}/{tot_target} · 缺口 {tot_deficit} · {len(plats)} 池")
    L.append(f"待重登母号 {len(stale)} · 无效母号 {invalid_n} · 邮箱池剩 {email_unused}"
             + ("  ⚠偏低!" if email_unused < warn else ""))
    report = "\n".join(L) + "\n" + "\n".join(blocks)
    if actions:
        report += "\n— 全局执行 —\n" + "\n".join(actions)
    elif cfg["MODE"] == "active" and quiet:
        report += "\n(安静时段,本轮不执行 active 动作)"

    level, reasons = compute_alert(cfg, all_rows, invalid_n, email_unused, gateway_ok, agg_pending)
    if any_bad > 0:
        if level == "info":
            level = "warn"
        reasons.append(f"Sub2 坏号 {any_bad}")
    emoji = {"crit": "🔴", "warn": "🟡", "info": "🟢"}[level]
    report += f"\n— 状态 {emoji} —\n" + ("、".join(reasons) if reasons else "一切正常")
    do_push = should_alert(cfg, level, bool(actions) or any_bad > 0)
    print(report)
    print(push_bark(cfg, report, f"AdobeTeam {emoji} 巡航", do_push))


if __name__ == "__main__":
    main()
