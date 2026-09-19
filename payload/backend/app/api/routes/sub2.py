"""Sub2 账号管理 & 推送:对接下游 Sub2API 网关。

去重主依赖 Sub2 实存(list_existing 按 account_id/邮箱比对),避免"网关抖动→去重
静默关闭→重复推"和"单条失败永久漏推"。但 token/cookie 分叉号(access_token 身份
≠ cookie 解析身份)会被实存去重漏配、每轮重推成"更新"空转,故推送成功再打本地
sub2_pushed_at 兜底(只标 created/updated 成功的;失败的不标、下次自动重试)。
"""
from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud import adobe_member as member_crud, setting as setting_crud
from app.db.session import get_db
from app.models.adobe_account import AdobeAccount
from app.models.adobe_member import AdobeMember
from app.models.setting import Setting
from app.services import (
    adobe_admin, firefly, firefly_image, log_store, pool_login, proxy_pool, sub2_client,
)

router = APIRouter(prefix="/sub2", tags=["Sub2 推送"], dependencies=[Depends(get_current_user)])

REQUIRED_CREDITS = 4000.0

# ---- admin_token 应用层加密(Fernet,密钥由 SECRET_KEY 派生)----
import base64 as _b64  # noqa: E402
import hashlib as _hashlib  # noqa: E402
import json  # noqa: E402

from app.core.config import settings as _settings  # noqa: E402

_ENC_PREFIX = "enc:v1:"


def _fernet():
    from cryptography.fernet import Fernet
    key = _b64.urlsafe_b64encode(_hashlib.sha256((_settings.SECRET_KEY or "adobeteam").encode()).digest())
    return Fernet(key)


def _enc(plain: str) -> str:
    if not plain:
        return ""
    try:
        return _ENC_PREFIX + _fernet().encrypt(plain.encode()).decode()
    except Exception:  # noqa: BLE001
        return plain  # 加密不可用时退回明文(不阻断功能)


def _dec(stored: str) -> str:
    if not stored:
        return ""
    if stored.startswith(_ENC_PREFIX):
        try:
            return _fernet().decrypt(stored[len(_ENC_PREFIX):].encode()).decode()
        except Exception:  # noqa: BLE001
            return ""
    return stored  # 历史明文,兼容读取


def _log(level: str, msg: str) -> None:
    try:
        log_store.STORE.add(level, "sub2", msg)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------- 配置读写 ----------------------------
def _rows(db: Session) -> dict[str, str]:
    return {r.key: r.value for r in db.scalars(select(Setting)).all()}


def _set(db: Session, key: str, value: str) -> None:
    row = db.scalar(select(Setting).where(Setting.key == key))
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))


def _parse_group_ids(raw: str) -> list[int]:
    raw = (raw or "").replace("，", ",").replace(" ", ",")
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]


def _default_platform(r: dict[str, str]) -> str:
    """主平台:历史 sub2_platform(默认 adobe_gemini)。其余平台配置存 sub2_{platform}_* 键。"""
    return r.get("sub2_platform", "adobe_gemini") or "adobe_gemini"


def _get_config(db: Session, platform: str | None = None) -> dict:
    """读 Sub2 配置。platform 为 None 或主平台→原样(gemini,行为不变);
    非主平台(如 adobe_gpt)→共用同一网关/开关,仅分组/协议/前缀按 sub2_{platform}_* 键隔离。"""
    r = _rows(db)
    prim = _default_platform(r)
    cfg = {
        "enabled": r.get("sub2_enabled", "false").lower() == "true",
        "auto_push": r.get("sub2_auto_push", "false").lower() == "true",
        "base_url": r.get("sub2_base_url", ""),
        "admin_token": _dec(r.get("sub2_admin_token", "")),
        "platform": prim,
        "protocol": r.get("sub2_protocol", "default") or "default",
        "group_ids": _parse_group_ids(r.get("sub2_group_ids", "")),
        "group_ids_raw": r.get("sub2_group_ids", ""),
        "name_prefix": r.get("sub2_name_prefix", "adobe-gemini"),
        "rate_multiplier": r.get("sub2_rate_multiplier", "1"),
        "concurrency": (int(r.get("sub2_concurrency", "10")) if str(r.get("sub2_concurrency", "10")).strip().isdigit() else 10),
    }
    if platform and platform != prim:
        cfg["platform"] = platform
        cfg["protocol"] = r.get(f"sub2_{platform}_protocol", "default") or "default"
        cfg["group_ids_raw"] = r.get(f"sub2_{platform}_group_ids", "")
        cfg["group_ids"] = _parse_group_ids(cfg["group_ids_raw"])
        cfg["name_prefix"] = r.get(f"sub2_{platform}_name_prefix", platform)
    return cfg


DEFAULT_PLATFORM = "adobe_gemini"


def _platforms(db: Session) -> list[str]:
    """当前需自愈的平台集合(至少含主平台;其余来自有效母号的 platform 列),供 autopilot 逐平台跑。"""
    r = _rows(db)
    plats = {_default_platform(r)}
    try:
        for (p,) in db.execute(select(AdobeAccount.platform).distinct()):
            if p:
                plats.add(p)
    except Exception:  # noqa: BLE001
        pass
    return sorted(plats)


def _member_account_id(m: AdobeMember) -> str:
    try:
        return (firefly.extract_account_id(m.access_token) or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _existing_keys(cfg: dict) -> dict:
    """Sub2 实存账号的 account_id/邮箱集合(用于去重)。base/token 未配则 ok=False。"""
    if not cfg.get("base_url") or not cfg.get("admin_token"):
        return {"ok": False, "account_ids": set(), "emails": set(), "count": 0,
                "message": "未配置 Sub2 地址或令牌"}
    return sub2_client.list_existing(cfg, platform=cfg.get("platform") or "")


def _member_dedup_keys(m: AdobeMember) -> tuple[set[str], str]:
    """子号在 Sub2 的去重键集。Sub2 credentials.account_id 有 user_id / aa_id 两种形态,
    单靠 firefly.extract_account_id(单一形态)会漏配→已在库的号被当"待推"反复重推(#2a)。
    这里同时取 JWT 的 user_id、aa_id 与 firefly 抽取值,任一命中即视为已在库。"""
    email = (m.email or "").strip().lower()
    ids: set[str] = set()
    cl = _jwt_claims(m.access_token)
    for k in (cl.get("user_id"), cl.get("aa_id")):
        if k:
            ids.add(str(k).strip())
    fa = _member_account_id(m)
    if fa:
        ids.add(fa)
    return ids, email


def _candidates(db: Session, existing: dict, limit: int | None,
                platform: str | None = None) -> tuple[list[AdobeMember], int]:
    """待推新子号(积分达标、且不在 Sub2 实存里)。返回 (新号, 已在 Sub2 数)。
    platform 指定时,只取"其母号 platform==该平台"的子号(孤儿/导入子号无母号→归主平台),
    使不同平台的子号推到各自 Sub2 分组,互不串号。"""
    ex_ids = existing.get("account_ids", set())
    ex_em = existing.get("emails", set())
    plat_map: dict[int, str] | None = None
    if platform:
        plat_map = {a.id: (a.platform or DEFAULT_PLATFORM) for a in db.scalars(select(AdobeAccount))}
    q = (
        select(AdobeMember)
        .where(
            AdobeMember.is_admin == False,  # noqa: E712
            AdobeMember.registered == True,  # noqa: E712
            AdobeMember.access_token != "",
            AdobeMember.cookie != "",  # 只有带 cookie 的才能 import-cookie 成 express 可用号
            AdobeMember.sub2_pushed_at.is_(None),  # 已推送过的不再重推(兜底 Sub2 分叉漏配)
        )
        .order_by(AdobeMember.id)
    )
    new_rows: list[AdobeMember] = []
    in_sub2 = 0
    for m in db.scalars(q).all():
        try:
            if float(m.credits or 0) < REQUIRED_CREDITS:  # 按阈值判满号(≥门槛),不再要求正好==4000
                continue
        except (TypeError, ValueError):
            continue
        if plat_map is not None:
            mp = plat_map.get(m.admin_id, DEFAULT_PLATFORM)  # 无母号→归主平台,保持原有 gemini 流转
            if mp != platform:
                continue
        ids, email = _member_dedup_keys(m)
        if (ids & ex_ids) or (email and email in ex_em):
            in_sub2 += 1
            continue
        new_rows.append(m)
        if limit and len(new_rows) >= limit:
            break
    return new_rows, in_sub2


def _member_item(m: AdobeMember) -> dict:
    return {
        "id": m.id, "name": m.display_name or m.email, "email": m.email,
        "access_token": m.access_token, "device_token": m.device_token,
        "device_id": m.device_id, "cookie": m.cookie,
        "credits": m.credits, "expires_at": m.expires_at,
    }


def mark_pushed(db: Session, rows: list[AdobeMember], result) -> int:
    """把本批推送里 created/updated 成功的子号打 sub2_pushed_at,防止分叉号被反复重推。
    优先按返回的逐条 items[{index,status}] 精准打标;无逐条明细则整批成功(failed==0
    且有 created/updated)时全标。失败的不标,下次自动重试。rows 与本次 items 同序。"""
    if not isinstance(result, dict):
        return 0
    try:
        now = datetime.datetime.utcnow()
        marked = 0
        items = result.get("items")
        if isinstance(items, list) and items:
            for it in items:
                if not isinstance(it, dict):
                    continue
                idx = it.get("index")
                st = str(it.get("status") or "").lower()
                if isinstance(idx, int) and 0 <= idx < len(rows) and st in ("created", "updated"):
                    rows[idx].sub2_pushed_at = now
                    marked += 1
        else:
            done = int(result.get("created") or 0) + int(result.get("updated") or 0)
            if int(result.get("failed") or 0) == 0 and done > 0:
                for m in rows:
                    m.sub2_pushed_at = now
                    marked += 1
        if marked:
            db.commit()
        return marked
    except Exception:  # noqa: BLE001 打标失败绝不拖垮推送主链
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return 0


# ---------------------------- Schemas ----------------------------
class ConfigIn(BaseModel):
    enabled: bool | None = None
    auto_push: bool | None = None
    base_url: str | None = None
    admin_token: str | None = None
    platform: str | None = None
    protocol: str | None = None
    group_ids: str | None = None
    name_prefix: str | None = None
    rate_multiplier: str | None = None
    concurrency: str | None = None


class PushIn(BaseModel):
    limit: int | None = None
    dry_run: bool = True
    platform: str = ""   # 空=主平台(gemini)


class BatchIdsIn(BaseModel):
    account_ids: list[int] = []
    balance: bool = False
    platform: str = ""   # 空=主平台(gemini)


# ---------------------------- 配置路由 ----------------------------
@router.get("/config")
def get_config(db: Session = Depends(get_db)) -> dict:
    cfg = _get_config(db)
    return {
        "enabled": cfg["enabled"], "auto_push": cfg["auto_push"],
        "base_url": cfg["base_url"], "admin_token_set": bool(cfg["admin_token"]),
        "platform": cfg["platform"], "protocol": cfg["protocol"],
        "group_ids": cfg["group_ids_raw"], "name_prefix": cfg["name_prefix"],
        "rate_multiplier": cfg["rate_multiplier"], "concurrency": cfg.get("concurrency", 10),
    }


@router.put("/config")
def put_config(body: ConfigIn, db: Session = Depends(get_db)) -> dict:
    m = body.model_dump(exclude_unset=True)
    mapping = {
        "enabled": ("sub2_enabled", "bool"), "auto_push": ("sub2_auto_push", "bool"),
        "base_url": ("sub2_base_url", "str"), "platform": ("sub2_platform", "str"),
        "protocol": ("sub2_protocol", "str"), "group_ids": ("sub2_group_ids", "str"),
        "name_prefix": ("sub2_name_prefix", "str"), "rate_multiplier": ("sub2_rate_multiplier", "str"),
        "concurrency": ("sub2_concurrency", "str"),
    }
    for field, (key, kind) in mapping.items():
        if field in m and m[field] is not None:
            v = m[field]
            if field == "rate_multiplier":  # 只接受非负数字
                try:
                    v = str(float(v))
                    if float(v) < 0:
                        return {"ok": False, "message": "计费倍率必须 ≥ 0"}
                except (TypeError, ValueError):
                    return {"ok": False, "message": "计费倍率必须是数字"}
            _set(db, key, ("true" if v else "false") if kind == "bool" else str(v))
    if m.get("admin_token"):
        _set(db, "sub2_admin_token", _enc(m["admin_token"].strip()))
    db.commit()
    return get_config(db)


class PlatformConfigIn(BaseModel):
    platform: str                      # 目标平台,如 adobe_gpt(非主平台)
    group_ids: str | None = None       # 该平台在 Sub2 的分组 id(逗号分隔)
    name_prefix: str | None = None
    protocol: str | None = None        # 默认 default(18token)


@router.get("/platforms")
def list_platforms(db: Session = Depends(get_db)) -> dict:
    """列出各平台的 Sub2 分组配置(主平台读 sub2_*,其余读 sub2_{platform}_*)。
    网关/令牌/开关全平台共用主配置。"""
    out = []
    for p in _platforms(db):
        c = _get_config(db, p)
        out.append({"platform": p, "protocol": c["protocol"],
                    "group_ids": c["group_ids_raw"], "name_prefix": c["name_prefix"],
                    "is_primary": p == _default_platform(_rows(db))})
    return {"ok": True, "platforms": out}


@router.put("/platform-config")
def put_platform_config(body: PlatformConfigIn, db: Session = Depends(get_db)) -> dict:
    """设置某非主平台(如 adobe_gpt)在 Sub2 的分组/前缀/协议。主平台请用 /config。"""
    p = (body.platform or "").strip()
    if not p:
        return {"ok": False, "message": "缺少 platform"}
    if p == _default_platform(_rows(db)):
        return {"ok": False, "message": "主平台请用 /sub2/config 配置"}
    if body.group_ids is not None:
        _set(db, f"sub2_{p}_group_ids", str(body.group_ids))
    if body.name_prefix is not None:
        _set(db, f"sub2_{p}_name_prefix", str(body.name_prefix))
    if body.protocol is not None:
        _set(db, f"sub2_{p}_protocol", str(body.protocol))
    db.commit()
    c = _get_config(db, p)
    return {"ok": True, "platform": p, "protocol": c["protocol"],
            "group_ids": c["group_ids_raw"], "name_prefix": c["name_prefix"]}


@router.post("/test")
def test_conn(db: Session = Depends(get_db)) -> dict:
    r = sub2_client.test_connection(_get_config(db))
    if not r.get("ok"):
        _log("WARNING", f"测试连接失败:{r.get('message')}")
    return r


@router.get("/groups")
def groups(db: Session = Depends(get_db)) -> dict:
    r = sub2_client.list_groups(_get_config(db))
    if not r.get("ok"):
        _log("WARNING", f"获取分组失败:{r.get('message')}")
    return r


@router.get("/accounts")
def accounts(page: int = 1, size: int = 50, platform: str = "", db: Session = Depends(get_db)) -> dict:
    cfg = _get_config(db, platform or None)
    res = sub2_client.list_accounts_page(cfg, platform=cfg["platform"], page=page, size=size)
    if not res.get("ok"):
        _log("WARNING", f"拉账号列表失败:{res.get('message')}")
        return res
    items = res.get("items") or []
    if items:
        # 只按"本页"邮箱查库,避免每次分页都把整张 adobe_members/adobe_accounts
        # 全表连大字段(cookie/token)水合进来——只取需要的三列 + 引用到的母号。
        page_emails = {
            (it.get("name") or "").strip().lower()
            for it in items
            if (it.get("name") or "").strip()
        }
        by_email: dict[str, tuple[int, bool]] = {}  # email -> (admin_id, is_imported)
        if page_emails:
            for em, admin_id, is_imported in db.execute(
                select(AdobeMember.email, AdobeMember.admin_id, AdobeMember.is_imported)
                .where(func.lower(AdobeMember.email).in_(page_emails))
            ).all():
                key = (em or "").strip().lower()
                if key:
                    by_email.setdefault(key, (admin_id, bool(is_imported)))
        need_ids = {aid for (aid, imp) in by_email.values() if aid and not imp}
        admins: dict[int, str] = {}
        if need_ids:
            admins = {
                aid: aemail
                for aid, aemail in db.execute(
                    select(AdobeAccount.id, AdobeAccount.email).where(AdobeAccount.id.in_(need_ids))
                ).all()
            }
        for it in items:
            info = by_email.get((it.get("name") or "").strip().lower())
            if info is None:
                it["owner"] = ""
            else:
                admin_id, is_imported = info
                if is_imported:
                    it["owner"] = "(导入)"
                elif admin_id and admin_id in admins:
                    it["owner"] = admins[admin_id]
                else:
                    it["owner"] = ("母号#" + str(admin_id)) if admin_id else ""
    return res


@router.get("/pool-membership")
def pool_membership(platform: str = "", db: Session = Depends(get_db)) -> dict:
    """号池每个子号是否已在 Sub2 实存 —— 按 account_id/邮箱真实比对(与 _candidates 同规则),
    返回"已在库"的子号邮箱集合(小写)。供号池页/母号页给每行打"在库 Sub2 / 未推送"标。
    网关不可达时 ok=False,前端应显示中性态(Sub2 未连接),而不是把所有号误标未推送。"""
    cfg = _get_config(db)
    if platform:
        cfg = {**cfg, "platform": platform}
    ex = _existing_keys(cfg)
    if not ex.get("ok"):
        return {"ok": False, "platform": cfg.get("platform", ""), "in_sub2": [],
                "count": 0, "message": ex.get("message", "无法确认 Sub2 现有账号")}
    ex_ids = ex.get("account_ids", set())
    ex_em = ex.get("emails", set())
    in_sub2: set[str] = set()
    q = select(AdobeMember).where(
        AdobeMember.is_admin == False,  # noqa: E712  只看子号,母号镜像行不打标
        AdobeMember.email != "",
    )
    for m in db.scalars(q).all():
        email = (m.email or "").strip().lower()
        if not email:
            continue
        aid = _member_account_id(m)
        if (aid and aid in ex_ids) or (email in ex_em):
            in_sub2.add(email)
    return {"ok": True, "platform": cfg.get("platform", ""),
            "in_sub2": sorted(in_sub2), "count": len(in_sub2),
            "truncated": ex.get("truncated", False)}


def _jwt_claims(tok: str) -> dict:
    try:
        p = tok.split(".")[1]
        p += "=" * (-len(p) % 4)
        return json.loads(_b64.urlsafe_b64decode(p))
    except Exception:  # noqa: BLE001
        return {}


def _list_all_raw(cfg: dict) -> list | None:
    """分页拉该平台全部 Sub2 账号原始对象(含 extra 余额/上限)。网关任何失败返回 None(绝不当空处理)。
    每页带重试(应对 Cloudflare 限流),页间小憩避免被封。"""
    import time as _t
    base = sub2_client.api_base(cfg.get("base_url", ""))
    token = cfg.get("admin_token", "")
    platform = cfg.get("platform") or ""

    def _extract(data):
        d = data.get("data")
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for k in ("items", "list", "accounts", "data"):
                if isinstance(d.get(k), list):
                    return d[k]
        return None

    out: list = []
    for pg in range(1, 200):
        raw = None
        for attempt in range(3):
            try:
                code, raw = sub2_client._request(
                    "GET", f"{base}/admin/accounts?platform={platform}&page={pg}&page_size=100", token, timeout=40)
                if code == 200:
                    break
                raw = None
            except Exception:  # noqa: BLE001
                raw = None
            _t.sleep(1.2)
        if raw is None:
            return None
        try:
            lst = _extract(json.loads(raw))
        except Exception:  # noqa: BLE001
            return None
        if not lst:
            break
        out.extend(lst)
        _t.sleep(0.25)
    return out


def _member_key_map(db: Session) -> dict:
    """user_id / aa_id / 邮箱 → AdobeMember。三重匹配:Sub2 的 account_id 有 user_id 和 aa_id 两种形态。"""
    km: dict = {}
    for m in db.scalars(select(AdobeMember).where(
            AdobeMember.registered == True, AdobeMember.access_token != "")):  # noqa: E712
        cl = _jwt_claims(m.access_token)
        for k in (cl.get("user_id"), cl.get("aa_id"), (m.email or "").lower()):
            if k:
                km.setdefault(str(k).strip(), m)
    return km


class HealthCleanIn(BaseModel):
    dry_run: bool = True
    balance_floor: float = 100.0
    cap: int = 8
    refresh_first: bool = False   # 判定前先批量刷新全部 Sub2 号的 token+余额,基于最新值
    platform: str = ""            # 空=主平台(gemini);指定则只清该平台 Sub2 账号(与其母号隔离)


class LivenessCleanIn(BaseModel):
    member_ids: list[int] = []
    dry_run: bool = True
    cap: int = 3


@router.post("/health-clean")
def health_clean(body: HealthCleanIn, db: Session = Depends(get_db)) -> dict:
    """按余额自愈:Sub2 里 余额<floor 的、或 上限==10(刷新确认后仍是10)的残号 →
    从 Sub2 删除 + 踢出对应母号组织 + 删本地行(制造缺口好补号)。
    dry_run=True 只扫描报告不动手。网关不可达一律中止(绝不在抖动时删)。"""
    cfg = _get_config(db, body.platform or None)
    if not cfg.get("base_url") or not cfg.get("admin_token"):
        return {"ok": False, "message": "Sub2 未配置"}
    if body.refresh_first:
        _refresh_all_balances(cfg, subset=30)   # 轮转刷 30 个余额,减负载(全量每轮会把网关刷过载)
    accounts = _list_all_raw(cfg)
    if accounts is None:
        return {"ok": False, "message": "Sub2 网关不可达,已中止(不在抖动时删号)"}
    floor = body.balance_floor
    # 判活以 Sub2 的 temp_unschedulable_reason 为准——它记录账号"失败过真实生图/鉴权"的原因,
    # 比余额可靠(余额可能显示陈旧的正数,但 token 已失效根本出不了图)。
    #   含 oauth invalid / user_not_entitled / quota_exhausted = 真死 → 删(哪怕余额显示还有);
    #   原因为空 = 正常可调度,留(余额刷新失败只是网关/显示问题,Sub2 会自愈);
    #   余额兜底:status=ready 且 <floor 也删。
    dead, crippled, depleted, healthy, unknown = [], [], [], [], []
    for a in accounts:
        ex = a.get("extra") or {}
        bal = ex.get("adobe_credits_available")
        capv = ex.get("adobe_credits_total")
        stt = ex.get("adobe_balance_last_status")
        reason = (a.get("temp_unschedulable_reason") or "").lower()
        rec = {"sub2_id": a.get("id"), "bal": bal, "cap": capv,
               "aid": (a.get("credentials") or {}).get("account_id"),
               "email": (a.get("name") or "").strip().lower(), "reason": reason}
        if reason and any(m in reason for m in _DEAD_MARKERS):
            dead.append(rec)                         # 真死:失败过真实生图/鉴权
        elif stt == "ready" and capv == 10:
            crippled.append(rec)                     # 残号
        elif stt == "ready" and bal is not None and bal < floor:
            depleted.append(rec)                     # 确认枯竭(可信读数)
        elif bal is not None and bal >= floor:
            healthy.append(rec)                      # 有额度且没失败记录 → 留
        else:
            unknown.append(rec)                      # 读不到/临时问题 → 留(Sub2 自愈)
    # 只对残号(上限10)做一次确认刷新;unknown(Sub2 刷新失败/临时不可调度)一律保留不删——
    # 实测:这些号在母号管理里刷新成功、能出图、有额度,Sub2 刷不动只是网关/Cloudflare 过载,不代表号废。
    confirmed_crippled, recovered_unknown, dead_unknown = [], [], []   # 后两者恒空(不按 Sub2 状态删)
    crip_ids = [r["sub2_id"] for r in crippled]
    if crip_ids:
        try:
            sub2_client.batch_refresh(cfg, crip_ids, balance=False)
            sub2_client.batch_refresh(cfg, crip_ids, balance=True)
        except Exception:  # noqa: BLE001
            pass
        fresh = _list_all_raw(cfg) or []
        fmap = {a.get("id"): (a.get("extra") or {}) for a in fresh}
        for r in crippled:
            e2 = fmap.get(r["sub2_id"], {})
            if e2.get("adobe_balance_last_status") == "ready" and e2.get("adobe_credits_total") == 10:
                confirmed_crippled.append(r)
    # 死号防抖:失败原因需持续 ≥DEAD_DEBOUNCE_SEC 才真删,给 Adobe 授权/token 瞬时抖动自愈窗口。
    now_ts = time.time()
    try:
        with open(_DEAD_CONFIRM) as _f:
            seen = json.load(_f)
    except Exception:  # noqa: BLE001
        seen = {}
    new_seen, confirmed_dead = {}, []
    for r in dead:
        sid = str(r["sub2_id"])
        first = float(seen.get(sid, now_ts))
        new_seen[sid] = first
        if now_ts - first >= DEAD_DEBOUNCE_SEC:
            confirmed_dead.append(r)
    try:
        with open(_DEAD_CONFIRM, "w") as _f:
            json.dump(new_seen, _f)
    except Exception:  # noqa: BLE001
        pass
    dead_pending = len(dead) - len(confirmed_dead)

    to_delete = confirmed_dead + confirmed_crippled + depleted
    km = _member_key_map(db)
    admins = {a.id: a for a in db.scalars(select(AdobeAccount))}
    for r in to_delete:
        m = km.get((r.get("aid") or "").strip()) or km.get(r.get("email") or "")
        r["admin_id"] = m.admin_id if m else None
        r["_m"] = m
    cleaned, affected = [], set()
    if not body.dry_run:
        st = setting_crud.get_settings(db)
        proxy_raw = st.proxy_url if (st.proxy_enabled and (st.proxy_url or "").strip()) else ""
        for r in to_delete[: max(0, body.cap)]:
            try:
                res = sub2_client.delete_account(cfg, r["sub2_id"])
                if not res.get("ok"):
                    _log("WARNING", f"health-clean Sub2 删除失败,本轮跳过(下轮重试):"
                                    f"#{r.get('sub2_id')} code={res.get('code')}")
                    continue   # Sub2 没删成功 → 绝不踢母号/删本地,保持三方一致
                m = r.get("_m")
                if m is not None:
                    acc = admins.get(m.admin_id)
                    if acc and acc.admin_token and acc.org_id:
                        kicked = False
                        for px in ([proxy_pool.next_proxy(proxy_raw) for _ in range(2)]
                                   if proxy_raw else []) + [""]:
                            try:
                                rr = adobe_admin.remove_member(token=acc.admin_token, org_id=acc.org_id,
                                                               email=m.email, proxy_url=px)
                                if rr.get("ok") or "未找到" in (rr.get("message") or ""):
                                    kicked = True
                                    break
                            except Exception:  # noqa: BLE001
                                continue
                        if not kicked:
                            _log("WARNING", f"health-clean 踢母号成员失败(Sub2 已删,仍删本地防重推):{m.email}")
                    affected.add(m.admin_id)
                    db.delete(m)
                cleaned.append(r["sub2_id"])
            except Exception as e:  # noqa: BLE001
                db.rollback()
                _log("WARNING", f"health-clean 删 {r.get('sub2_id')} 失败:{e}")
        db.commit()
    admin_set = affected or {r["admin_id"] for r in to_delete if r["admin_id"]}
    deficits = {}
    for aid in admin_set:
        if aid:
            regd = member_crud.count_registered_with_credit(db, aid, REQUIRED_CREDITS)
            deficits[str(aid)] = max(0, 9 - regd)
    return {"ok": True, "dry_run": body.dry_run, "scanned": len(accounts),
            "healthy": len(healthy), "dead": len(confirmed_dead), "dead_pending": dead_pending,
            "crippled": len(confirmed_crippled), "depleted": len(depleted),
            "unknown": len(unknown), "to_delete": len(to_delete), "cleaned": len(cleaned),
            "affected_admins": sorted(a for a in admin_set if a), "deficits": deficits}


_BAL_CURSOR = "/opt/adobeteam/.bal_refresh_cursor"

import time  # noqa: E402
_DEAD_CONFIRM = "/opt/adobeteam/.dead_confirm.json"
DEAD_DEBOUNCE_SEC = 300  # 死号失败原因需持续 ≥5 分钟(跨一轮扫描)才真删,防 Adobe 瞬时抖动误删

# Sub2 temp_unschedulable_reason 里代表"真死"的标记(失败过真实生图/鉴权,不会自愈):
_DEAD_MARKERS = (
    "oauth token is not valid",   # 401 token 失效
    "token is not valid",
    "user_not_entitled",          # 403 无产品授权(母号踢了/组织没了)
    "not entitled",
    "quota_exhausted",            # 403 额度耗尽
)


def _refresh_all_balances(cfg: dict, subset: int = 0) -> dict:
    """分块批量刷新 Sub2 余额(best-effort,只刷余额)。subset>0 时只刷一个轮转子集,
    减轻 Sub2/Cloudflare 负载——避免自己把网关刷过载,反而让余额刷新失败、号被标'临时不可调度'。"""
    raw = _list_all_raw(cfg)
    if not raw:
        return {"refreshed": 0}
    ids = sorted(a.get("id") for a in raw if a.get("id") is not None)
    if subset and 0 < subset < len(ids):
        cur = 0
        try:
            with open(_BAL_CURSOR) as f:
                cur = int(f.read().strip())
        except Exception:  # noqa: BLE001
            cur = 0
        start = next((i for i, x in enumerate(ids) if x > cur), 0)
        picked = ids[start:start + subset]
        if len(picked) < subset:
            picked += ids[: subset - len(picked)]   # 环绕
        try:
            with open(_BAL_CURSOR, "w") as f:
                f.write(str(picked[-1]))
        except Exception:  # noqa: BLE001
            pass
        ids = picked
    done = 0
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        try:
            sub2_client.batch_refresh(cfg, chunk, balance=True)
            done += len(chunk)
        except Exception:  # noqa: BLE001
            continue
    return {"refreshed": done}


# 测活结果分级:瞬时/基础设施 → 绝不判死;明确失败 → 死
_LIVENESS_TRANSIENT = ("繁忙", "system under load", "超时", "无响应", "未返回轮询",
                       "轮询时 token 失效", "测活异常")
_LIVENESS_DEAD = ("额度已耗尽", "taste_exhausted", "token 失效或无权限",
                  "出图失败", "FAILED", "CANCELLED", "ERROR")


def _liveness_verdict(res: dict) -> str:
    if res.get("success"):
        return "alive"
    msg = str(res.get("message") or "")
    if any(m in msg for m in _LIVENESS_TRANSIENT):
        return "inconclusive"
    if any(m in msg for m in _LIVENESS_DEAD):
        return "dead"
    return "inconclusive"   # 未知一律保守,绝不误删


def _sub2_id_map(cfg: dict):
    """{account_id / 邮箱 → Sub2 数字 id},定位子号对应的 Sub2 账号。gateway 失败→None。"""
    raw = _list_all_raw(cfg)
    if raw is None:
        return None
    m: dict = {}
    for a in raw:
        sid = a.get("id")
        if sid is None:
            continue
        aid = (a.get("credentials") or {}).get("account_id")
        em = (a.get("name") or "").strip().lower()
        for k in (aid, em):
            if k:
                m.setdefault(str(k).strip(), sid)
    return m


@router.post("/liveness-clean")
def liveness_clean(body: LivenessCleanIn, db: Session = Depends(get_db)) -> dict:
    """定期测活:先刷 token 再真出图;刷新后仍出不了图且是明确失败 = 死号 →
    删 Sub2 + 踢母号 + 删本地(制造缺口好补)。dry_run=True 只测+报告不删。
    刷 token 这一步同时满足"定期刷新 token"。瞬时/过载一律判存疑,绝不误删。"""
    cfg = _get_config(db)
    st = setting_crud.get_settings(db)
    proxy_raw = st.proxy_url if (st.proxy_enabled and (st.proxy_url or "").strip()) else ""
    ids = list(dict.fromkeys(body.member_ids))[: max(0, body.cap)]
    alive, incon, refreshed, dead, details = 0, 0, 0, [], []
    for mid in ids:
        m = member_crud.get(db, mid)
        if not m or m.is_admin:
            continue
        rr = {"success": False, "message": ""}
        try:
            rr = pool_login.refresh_one_sync(mid) or rr
            if rr.get("success"):
                refreshed += 1
        except Exception as e:  # noqa: BLE001
            rr = {"success": False, "message": str(e)[:80]}
        db.refresh(m)
        token = (m.access_token or "").strip()
        if not token:
            incon += 1
            details.append({"id": mid, "verdict": "no_token"})
            continue
        # 关键防误删:token 刷新没成功 → 测的是旧 token,失败不可信 → 一律存疑,绝不判死
        if not rr.get("success"):
            incon += 1
            details.append({"id": mid, "email": m.email, "verdict": "inconclusive",
                            "msg": "token 刷新失败(" + str(rr.get("message") or "")[:40] + ")"})
            continue
        try:
            res = firefly_image.test_generate(
                access_token=token, arp_session_id=m.arp_session_id or "",
                proxy_url=proxy_pool.pick(st), timeout=120)
        except Exception as e:  # noqa: BLE001
            res = {"success": False, "message": f"测活异常:{e}"}
        v = _liveness_verdict(res)
        details.append({"id": mid, "email": m.email, "verdict": v,
                        "msg": str(res.get("message") or "")[:80]})
        if v == "alive":
            alive += 1
        elif v == "dead":
            dead.append(m)
        else:
            incon += 1

    cleaned, affected = [], set()
    if not body.dry_run and dead:
        idmap = _sub2_id_map(cfg)
        if idmap is None:
            return {"ok": False, "message": "Sub2 网关不可达,已测活但不删(防误删)",
                    "tested": len(ids), "alive": alive, "dead": len(dead),
                    "inconclusive": incon, "cleaned": 0, "refreshed": refreshed,
                    "deficits": {}, "details": details}
        admins = {a.id: a for a in db.scalars(select(AdobeAccount))}
        for m in dead:
            try:
                key = (_member_account_id(m) or (m.email or "").lower())
                sid = idmap.get(str(key).strip()) or idmap.get((m.email or "").lower())
                if sid is not None:
                    sub2_client.delete_account(cfg, sid)
                acc = admins.get(m.admin_id)
                if acc and acc.admin_token and acc.org_id:
                    for px in ([proxy_pool.next_proxy(proxy_raw) for _ in range(2)]
                               if proxy_raw else []) + [""]:
                        try:
                            adobe_admin.remove_member(token=acc.admin_token, org_id=acc.org_id,
                                                      email=m.email, proxy_url=px)
                            break
                        except Exception:  # noqa: BLE001
                            continue
                affected.add(m.admin_id)
                db.delete(m)
                cleaned.append(m.id)
            except Exception as e:  # noqa: BLE001
                db.rollback()
                _log("WARNING", f"liveness-clean 删 member {m.id} 失败:{e}")
        db.commit()

    admin_set = affected or {m.admin_id for m in dead}
    deficits = {}
    for aid in admin_set:
        if aid:
            regd = member_crud.count_registered_with_credit(db, aid, REQUIRED_CREDITS)
            deficits[str(aid)] = max(0, 9 - regd)
    return {"ok": True, "dry_run": body.dry_run, "tested": len(ids),
            "alive": alive, "dead": len(dead), "inconclusive": incon,
            "cleaned": len(cleaned), "refreshed": refreshed,
            "affected_admins": sorted(a for a in admin_set if a),
            "deficits": deficits, "details": details}


@router.get("/account-ids")
def account_ids(platform: str = "", db: Session = Depends(get_db)) -> dict:
    cfg = _get_config(db, platform or None)
    full = sub2_client.list_accounts_full(cfg, platform=cfg["platform"])
    if not full.get("ok"):
        _log("WARNING", f"拉全部账号 id 失败:{full.get('message')}")
    ids = [a["id"] for a in full.get("accounts", []) if a.get("id") is not None]
    return {"ok": full.get("ok", False), "ids": ids, "count": len(ids),
            "truncated": full.get("truncated", False), "message": full.get("message", "")}


@router.get("/candidates")
def candidates(platform: str = "", db: Session = Depends(get_db)) -> dict:
    cfg = _get_config(db, platform or None)
    existing = _existing_keys(cfg)
    if not existing.get("ok"):
        return {"new_count": 0, "in_sub2": 0, "sub2_total": 0, "sub2_ok": False,
                "message": existing.get("message", "无法确认 Sub2 现有账号")}
    rows, in_sub2 = _candidates(db, existing, None, platform=cfg["platform"])
    return {
        "new_count": len(rows), "in_sub2": in_sub2, "platform": cfg["platform"],
        "sub2_total": existing.get("count", 0), "sub2_ok": True,
        "sample": [{"id": m.id, "email": m.email, "credits": m.credits} for m in rows[:10]],
    }


@router.post("/batch-refresh")
def batch_refresh(body: BatchIdsIn, db: Session = Depends(get_db)) -> dict:
    cfg = _get_config(db, body.platform or None)
    if not body.account_ids:
        return {"ok": False, "message": "未选择账号"}
    r = sub2_client.batch_refresh(cfg, body.account_ids, balance=body.balance)
    if not r.get("ok"):
        _log("ERROR", f"批量{'刷额度' if body.balance else '刷token'}失败:{r.get('message') or r.get('code')}")
    return r


@router.post("/batch-delete")
def batch_delete(body: BatchIdsIn, db: Session = Depends(get_db)) -> dict:
    cfg = _get_config(db, body.platform or None)
    if not body.account_ids:
        return {"ok": False, "message": "未选择账号"}
    deleted, failed = 0, 0
    for sid in body.account_ids:
        if sub2_client.delete_account(cfg, sid).get("ok"):
            deleted += 1
        else:
            failed += 1
    ok = failed == 0
    if not ok:
        _log("ERROR", f"批量删除:成功 {deleted} 失败 {failed}")
    return {"ok": ok, "deleted": deleted, "failed": failed,
            "message": f"删除 {deleted} · 失败 {failed}"}


@router.post("/push")
def push(body: PushIn, db: Session = Depends(get_db)) -> dict:
    cfg = _get_config(db, body.platform or None)
    if not cfg["base_url"] or not cfg["admin_token"]:
        return {"ok": False, "message": "请先配置 Sub2API 地址与 admin_token"}
    if not cfg["group_ids"]:
        return {"ok": False, "message": "请先填写要绑定的 group_ids"}

    existing = _existing_keys(cfg)
    if not existing.get("ok"):
        _log("ERROR", f"推送前无法确认 Sub2 现有账号,已中止:{existing.get('message')}")
        return {"ok": False, "message": "无法确认 Sub2 现有账号(网关不可达/令牌失效?),"
                                        "已中止推送以防重复。请先「测试连接」。"}

    rows, in_sub2 = _candidates(db, existing, body.limit, platform=cfg["platform"])
    if not rows:
        return {"ok": True, "dry_run": body.dry_run, "new_count": 0, "in_sub2": in_sub2,
                "message": f"没有新的可用子号(Sub2 已有 {in_sub2} 个匹配,已跳过)"}

    if body.dry_run:
        return {
            "ok": True, "dry_run": True, "new_count": len(rows), "in_sub2": in_sub2,
            "platform": cfg["platform"], "group_ids": cfg["group_ids"],
            "message": f"将推送 {len(rows)} 个新子号(Sub2 已有 {in_sub2},已跳过)",
            "sample": [{"id": m.id, "email": m.email} for m in rows[:10]],
        }

    items = [_member_item(m) for m in rows]
    resp = sub2_client.import_tokens({**cfg, "concurrency": cfg.get("concurrency", 10)}, items)
    result = resp.get("result") or {}
    ok = resp.get("code") == 200
    created = int(result.get("created") or 0) if isinstance(result, dict) else 0
    failed = int(result.get("failed") or 0) if isinstance(result, dict) else 0
    if not ok:
        _log("ERROR", f"推送失败 HTTP {resp.get('code')}:{resp.get('message')}")
    marked = mark_pushed(db, rows, result)  # 打标已入库,兜底 Sub2 分叉漏配
    return {
        "ok": ok, "dry_run": False, "attempted": len(rows),
        "created": created, "failed": failed, "marked": marked,
        "http_code": resp.get("code"), "message": resp.get("message") or "",
        "result": result if isinstance(result, dict) else {"raw": str(result)[:400]},
    }
