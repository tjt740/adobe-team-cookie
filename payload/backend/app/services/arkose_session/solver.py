"""Same-session Arkose solver: PoW + gfct + YesCaptcha classify + /fc/ca/.

The harvest browser only starts gt2. Classification is FunCaptchaClassification.
Do not open a second FunCaptcha widget.
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from app.services.arkose_session.bio import build_bio_payload, gen_mouse_segment
from app.services.arkose_session.classify import (
    UnknownQuestion,
    classify_yes_wave,
)
from app.services.arkose_session.crypt import (
    compact_json,
    decrypt_challenge_image,
    encrypt_arkose,
    is_image_magic,
)
from app.services.arkose_session.harvest import (
    HarvestSeed,
    NavigationFailed,
    harvest_gt2,
)
from app.services.arkose_session.node import run_pow, run_tguess
from app.services.arkose_session.questions import spec_for_game
from app.services.arkose_session.util import (
    ark_quote,
    chrome_major,
    clip,
    first_non_empty,
    form_encode,
)

LogFn = Callable[[str], None]

SIGNUP_PUBLIC_KEY = "436DD567-5435-4B14-89A6-2F1188E11334"
SIGNUP_SURL = "https://arks-client.adobe.com"
DEFAULT_ENFORCEMENT_HASH = "7456a189e914d8deb04e91bbcc80b059"
DEFAULT_GAMECORE = "1.34.1"


class SessionSolveError(RuntimeError):
    pass


@dataclass
class SessionResult:
    token: str
    cookies: list[dict[str, str]] = field(default_factory=list)
    suppressed: bool = False
    via: str = "yescaptcha-session"


@dataclass
class ArkoseToken:
    raw: str
    session: str = ""
    sid: str = "ap-southeast-1"
    at: str = "40"
    pk: str = ""
    surl: str = SIGNUP_SURL
    lang: str = "en"
    meta: str = "3"
    meta_w: str = "400"
    meta_h: str = "303"
    ag: str = "101"
    parts: dict[str, str] = field(default_factory=dict)


def parse_arkose_token(tok: str) -> ArkoseToken:
    p = ArkoseToken(raw=tok)
    segs = (tok or "").split("|")
    if segs:
        p.session = segs[0]
        if p.session.startswith("token="):
            p.session = p.session[len("token="):]
    for seg in segs[1:]:
        if "=" not in seg:
            continue
        k, v = seg.split("=", 1)
        try:
            v = unquote(v)
        except Exception:
            pass
        p.parts[k] = v
        if k == "r":
            p.sid = v
        elif k == "at":
            p.at = v
        elif k == "pk":
            p.pk = v
        elif k == "surl":
            p.surl = v.rstrip("/")
        elif k == "lang":
            p.lang = v
        elif k == "meta":
            p.meta = v
        elif k == "meta_width":
            p.meta_w = v
        elif k == "meta_height":
            p.meta_h = v
        elif k == "ag":
            p.ag = v
    if not p.surl:
        p.surl = SIGNUP_SURL
    return p


def arid_from(seed: HarvestSeed) -> str:
    if (seed.arid or "").strip():
        return seed.arid.strip()
    for c in seed.cookies:
        if str(c.get("name") or "").upper() == "ARID" and c.get("value"):
            return str(c["value"])
    return ""


class ArkoseHTTP:
    def __init__(self, proxy: str, ua: str):
        from app.services.adobe_protocol.http_client import HttpClient

        self.client = HttpClient(proxy)
        if ua:
            self.client.user_agent = ua
            major = chrome_major(ua)
            if major:
                self.client._chrome_major = major
                self.client._sec_ch_ua = (
                    f'"Chromium";v="{major}", '
                    f'"Google Chrome";v="{major}", "Not/A)Brand";v="99"'
                )

    def do(
        self, method: str, url: str, body: bytes | str | None = None,
        headers: dict[str, str] | None = None, timeout: int = 90,
    ) -> tuple[int, bytes, dict[str, str]]:
        h = self.client._base_headers()
        if headers:
            h.update(headers)
        resp = self.client.session.request(
            method, url, headers=h, data=body, timeout=timeout, allow_redirects=True,
        )
        self.client._merge_cookies_from_resp(resp)
        hdr = {str(k): str(v) for k, v in resp.headers.items()}
        return resp.status_code, resp.content or b"", hdr

    def set_cookie(self, name: str, value: str, domain: str = "", path: str = "/") -> None:
        if not name or not value:
            return
        self.client.cookies[name] = value
        kw: dict[str, str] = {}
        if domain:
            kw["domain"] = domain.lstrip(".")
        if path:
            kw["path"] = path
        try:
            self.client.session.cookies.set(name, value, **kw)
        except Exception:
            try:
                self.client.session.cookies.set(name, value)
            except Exception:
                pass


def inject_harvest_cookies(http: ArkoseHTTP, cookies: list[dict[str, str]]) -> None:
    for ck in cookies:
        name = str(ck.get("name") or "").strip()
        value = str(ck.get("value") or "").strip()
        if not name or not value:
            continue
        domain = str(ck.get("domain") or "")
        path = str(ck.get("path") or "/")
        http.set_cookie(name, value, domain=domain, path=path)


def arkose_headers(origin: str, referer: str) -> dict[str, str]:
    return {
        "Accept": "*/*",
        "Origin": origin,
        "Referer": referer,
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Cache-Control": "no-cache",
    }


def newrelic_ts() -> str:
    return str(int(time.time() * 1000) * 100)


def arkose_timestamp() -> tuple[str, str]:
    t = str(int(time.time() * 1000)).ljust(13, "0")[:13]
    v = t[:7] + "00" + t[7:13]
    return v, v


def enforcement_url(surl: str, observed: str = "") -> str:
    if (observed or "").strip():
        return observed.strip().split("?", 1)[0]
    return f"{surl.rstrip('/')}/v2/4.2.2/enforcement.{DEFAULT_ENFORCEMENT_HASH}.html"


def game_core_url(surl: str, tok: ArkoseToken, pk: str, version: str = DEFAULT_GAMECORE) -> str:
    from urllib.parse import urlencode

    q = urlencode({
        "session": tok.session,
        "r": tok.sid,
        "meta": tok.meta,
        "lang": tok.lang,
        "pk": pk,
        "at": tok.at,
    })
    return f"{surl.rstrip('/')}/fc/assets/ec-game-core/game-core/{version}/standard/index.html?{q}"


def game_core_referer(surl: str, tok: ArkoseToken, pk: str, version: str = DEFAULT_GAMECORE) -> str:
    pairs = [
        ("session", tok.session),
        ("r", tok.sid),
        ("meta", tok.meta),
        ("meta_width", tok.meta_w),
        ("meta_height", tok.meta_h),
        ("metabgclr", first_non_empty(tok.parts.get("metabgclr", ""), "transparent")),
        ("metaiconclr", first_non_empty(tok.parts.get("metaiconclr", ""), "#555555")),
        ("guitextcolor", first_non_empty(tok.parts.get("guitextcolor", ""), "#000000")),
        ("lang", tok.lang),
        ("pk", pk),
        ("at", tok.at),
        ("ag", tok.ag),
        ("cdn_url", f"{surl.rstrip('/')}/cdn/fc"),
        ("surl", surl),
        ("smurl", f"{surl.rstrip('/')}/cdn/fc/assets/style-manager"),
    ]
    q = "&".join(f"{k}={ark_quote(v)}" for k, v in pairs)
    return f"{surl.rstrip('/')}/fc/assets/ec-game-core/game-core/{version}/standard/index.html?{q}"


def gfct_body(session: str, sid: str, at: str) -> str:
    return form_encode(
        "token", session,
        "sid", sid,
        "render_type", "canvas",
        "lang", "en",
        "isAudioGame", "false",
        "is_compatibility_mode", "false",
        "apiBreakerVersion", "green",
        "analytics_tier", at,
    )


class SessionSolver:
    def __init__(
        self,
        api_key: str,
        proxy_url: str = "",
        user_agent: str = "",
        log: LogFn | None = None,
        http: ArkoseHTTP | None = None,
        classify=None,
        pow_fn=None,
        tguess_fn=None,
    ):
        self.api_key = api_key
        self.proxy_url = proxy_url
        self.user_agent = user_agent
        self.log = log if callable(log) else (lambda _m: None)
        self.http = http
        self.classify = classify
        self.pow_fn = pow_fn
        self.tguess_fn = tguess_fn
        self.gamecore = os.environ.get("ADOBE_ARKOSE_GAMECORE") or DEFAULT_GAMECORE

    def continue_session(self, seed: HarvestSeed, *, public_key: str = "", surl: str = "") -> SessionResult:
        tok = parse_arkose_token(seed.token)
        arid = arid_from(seed)
        if not arid:
            raise SessionSolveError("arkose-session: missing ARID")
        ua = first_non_empty(seed.user_agent, self.user_agent)
        pk = first_non_empty(public_key, tok.pk, SIGNUP_PUBLIC_KEY)
        tok.surl = first_non_empty(tok.surl, surl, SIGNUP_SURL).rstrip("/")
        http = self.http or ArkoseHTTP(self.proxy_url, ua)
        inject_harvest_cookies(http, seed.cookies)
        http.set_cookie("ARID", arid, domain=urlparse(tok.surl).hostname or "arks-client.adobe.com")

        enf = enforcement_url(tok.surl, seed.enforcement)
        base = arkose_headers(tok.surl, enf)
        self.log(
            f"gt2 not suppressed, session-solve pk={pk} region={tok.sid} "
            f"token_len={len(seed.token)} arid=1 ua={clip(ua, 80)}"
        )

        skip_pow = seed.pow is False
        try:
            self._run_pow_gate(http, tok, base, skip_pow)
        except _PowSetup400:
            if seed.pow is not True:
                self.log("pows/setup 400, skip pow")
            else:
                raise

        init_url = f"{tok.surl}/fc/init-load/?session_token={ark_quote(tok.session)}"
        http.do("GET", init_url, headers=dict(base))
        gc = game_core_url(tok.surl, tok, pk, self.gamecore)
        http.do("GET", gc, headers=dict(base))

        gfct_hdr = dict(base)
        gfct_hdr["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        gfct_hdr["X-Requested-With"] = "XMLHttpRequest"
        gfct_hdr["X-Newrelic-Timestamp"] = newrelic_ts()
        st, raw, _ = http.do(
            "POST", f"{tok.surl}/fc/gfct/", gfct_body(tok.session, tok.sid, tok.at), gfct_hdr,
        )
        if b"DENIED" in raw:
            raise SessionSolveError(f"gfct DENIED: {clip(raw, 160)}")
        if st != 200:
            raise SessionSolveError(f"gfct {st}: {clip(raw, 160)}")
        try:
            game = json.loads(raw)
        except Exception as e:
            raise SessionSolveError(f"gfct json: {clip(raw, 160)}") from e
        session_token = str(game.get("session_token") or "")
        challenge_id = str(game.get("challengeID") or "")
        if not session_token or not challenge_id:
            raise SessionSolveError("gfct missing session/challenge")
        gdata = game.get("game_data") or {}
        instruction = str(gdata.get("instruction_string") or "")
        variant = first_non_empty(instruction, str(gdata.get("game_variant") or ""))
        gui = gdata.get("customGUI") or {}
        imgs = list(gui.get("_challenge_imgs") or [])
        waves = int(gdata.get("waves") or 0) or len(imgs) or 1
        difficulty = int(gdata.get("game_difficulty") or 0)
        game_type = int(gdata.get("gameType") or 0)
        self.log(
            f"session-solve variant={variant} waves={waves} gameType={game_type} "
            f"difficulty={difficulty}"
        )

        dapib = ""
        dapib_url = str(game.get("dapib_url") or "")
        if dapib_url:
            st, db, _ = http.do("GET", dapib_url, headers=arkose_headers(tok.surl, tok.surl + "/"))
            if st == 200:
                dapib = db.decode("utf-8", "replace")

        core_ref = game_core_referer(tok.surl, tok, pk, self.gamecore)
        self._post_fc_a(http, tok, game, enf, core_ref, "Site URL", enf, False)
        self._post_fc_a(http, tok, game, enf, core_ref, "loaded", "game loaded", False)
        self._post_fc_a(http, tok, game, enf, core_ref, "begin app", "user clicked verify", True)

        spec = spec_for_game(instruction, str(gdata.get("game_variant") or ""))
        history: list[dict[str, int]] = []
        prev_id: Any = None
        bio_accum = ""
        bio_t = 900 + random.randint(0, 1700)
        ch_tok = session_token
        last_detail = ""
        last_ca: dict[str, Any] = {}

        for wave in range(waves):
            if not imgs:
                raise SessionSolveError(f"session-solve: no image for wave {wave + 1}")
            st, img_raw, _ = http.do(
                "GET", imgs[0], headers=arkose_headers(tok.surl, tok.surl + "/"),
            )
            if st != 200:
                raise SessionSolveError(f"challenge image {st}")
            img_raw = self._decrypt_image(http, tok, ch_tok, challenge_id, img_raw)
            tiles = difficulty if difficulty > 0 else spec.cols
            idx, task_id = self._classify(
                img_raw, spec, tiles, instruction, str(gdata.get("game_variant") or ""), prev_id,
            )
            prev_id = task_id
            self.log(
                f"session-solve wave={wave + 1}/{waves} classify=yescaptcha "
                f"index={idx} taskId={task_id}"
            )
            history.append({"index": idx})
            guess_plain = compact_json(history)
            guess_enc = encrypt_arkose(guess_plain, ch_tok)
            req_id = encrypt_arkose("{}", "REQUESTED" + ch_tok + "ID")
            tguess = ""
            if dapib:
                try:
                    fn = self.tguess_fn or run_tguess
                    tguess = fn(ch_tok, guess_plain, dapib)
                except Exception as e:  # noqa: BLE001
                    self.log(f"tguess skip: {clip(str(e), 160)}")
            seg, bio_t = gen_mouse_segment(bio_t)
            bio_accum += seg
            bio = build_bio_payload(bio_accum)
            ts_hdr, ts_cookie = arkose_timestamp()
            http.set_cookie("timestamp", ts_cookie, domain=urlparse(tok.surl).hostname or "")

            ca = form_encode(
                "session_token", ch_tok,
                "game_token", challenge_id,
                "sid", tok.sid,
                "guess", guess_enc,
                "render_type", "canvas",
                "analytics_tier", tok.at,
                "is_compatibility_mode", "false",
                "ecdata", _b64('{"height":450,"width":400}'),
                "bio", bio,
            )
            if tguess:
                ca += "&tguess=" + ark_quote(tguess)
            ca_hdr = dict(base)
            ca_hdr["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
            ca_hdr["X-Requested-With"] = "XMLHttpRequest"
            ca_hdr["X-Requested-Id"] = req_id
            ca_hdr["X-Newrelic-Timestamp"] = ts_hdr
            ca_hdr["Referer"] = core_ref
            st, ca_raw, _ = http.do("POST", f"{tok.surl}/fc/ca/", ca, ca_hdr)
            if st != 200:
                raise SessionSolveError(f"fc/ca {st}: {clip(ca_raw, 160)}")
            try:
                answered = json.loads(ca_raw)
            except Exception as e:
                raise SessionSolveError(f"fc/ca json: {clip(ca_raw, 160)}") from e
            if not isinstance(answered, dict):
                answered = {}
            next_imgs = _ca_next_images(answered)
            detail = (
                f"wave={wave + 1}/{waves} index={idx} tguess={bool(tguess)} "
                f"ca response={answered.get('response')!r} solved={bool(answered.get('solved'))} "
                f"next_imgs={len(next_imgs)}"
            )
            last_detail = detail
            last_ca = answered
            self.log(f"session-solve {detail}")
            if answered.get("response") == "answered" and answered.get("solved"):
                self.log(f"ca solved waves={wave + 1} tguess={bool(tguess)}")
                return SessionResult(
                    token=seed.token, cookies=seed.cookies, suppressed=False,
                )
            if not next_imgs:
                raise SessionSolveError(_ca_unsolved(answered, detail))
            imgs = next_imgs
        if last_detail:
            raise SessionSolveError(_ca_unsolved(last_ca, last_detail))
        raise SessionSolveError(f"session-solve: not solved after {waves} waves")

    def _classify(self, img: bytes, spec, tiles: int, instruction: str, variant: str, prev) -> tuple[int, Any]:
        if self.classify:
            return self.classify(img, spec, tiles, instruction, variant, prev)
        return classify_yes_wave(
            api_key=self.api_key,
            img=img,
            instruction=instruction,
            game_variant=variant,
            tiles=tiles,
            rotate=spec.rotate,
            proxy_url=self.proxy_url,
            log=self.log,
        )

    def _decrypt_image(
        self, http: ArkoseHTTP, tok: ArkoseToken, ch_tok: str, game_token: str, raw: bytes,
    ) -> bytes:
        if is_image_magic(raw):
            return raw
        trim = raw.strip()
        if not trim or trim[:1] != b"{":
            return raw
        ek = form_encode("session_token", ch_tok, "game_token", game_token)
        h = arkose_headers(tok.surl, tok.surl + "/")
        h["Content-Type"] = "application/x-www-form-urlencoded"
        st, body, _ = http.do("POST", f"{tok.surl}/fc/ekey/", ek, h)
        if st != 200:
            raise SessionSolveError(f"ekey {st}: {clip(body, 120)}")
        try:
            obj = json.loads(body)
        except Exception:
            obj = {}
        key = str((obj or {}).get("decryption_key") or "")
        try:
            return decrypt_challenge_image(trim, key)
        except Exception as e:
            raise SessionSolveError(str(e)) from e

    def _run_pow_gate(self, http: ArkoseHTTP, tok: ArkoseToken, base: dict[str, str], skip: bool) -> None:
        if skip:
            return
        setup_url = f"{tok.surl}/pows/setup?session_token={ark_quote(tok.session)}"
        st, body, _ = http.do("GET", setup_url, headers=dict(base))
        if st == 400:
            raise _PowSetup400(clip(body, 180))
        if st != 200:
            raise SessionSolveError(f"pows/setup {st}: {clip(body, 180)}")
        try:
            setup = json.loads(body)
        except Exception as e:
            raise SessionSolveError(f"pows/setup json: {clip(body, 180)}") from e
        pow_token = str(setup.get("pow_token") or "")
        sequence = str(setup.get("sequence") or "")
        work = setup.get("work_config") or {}
        if not pow_token or not sequence:
            raise SessionSolveError("pows/setup missing pow_token/sequence")
        st, seq, _ = http.do("GET", sequence, headers=dict(base))
        if st != 200:
            raise SessionSolveError(f"pow sequence {st}: {clip(seq, 120)}")
        pow_run = self.pow_fn or run_pow
        for _round in range(7):
            payload = json.dumps({
                "session_token": tok.session,
                "pow_token": pow_token,
                "round": _round,
                "time": int(time.time() * 1000),
            }).encode("utf-8")
            hs = dict(base)
            hs["Content-Type"] = "application/json"
            hs["Referer"] = f"{tok.surl}/cdn/fc/assets/pow/2.4.0/compat/index.html"
            http.do("POST", f"{tok.surl}/pows/started", payload, hs)
            sol = pow_run(seq, work if isinstance(work, dict) else {})
            check = json.dumps({
                "pow_token": pow_token,
                "session_token": tok.session,
                "hash_rate": sol.get("hash_rate"),
                "execution_time": sol.get("execution_time"),
                "transform": sol.get("transform"),
                "result": sol.get("result"),
            }).encode("utf-8")
            h = dict(base)
            h["Content-Type"] = "text/plain;charset=UTF-8"
            st, resp, _ = http.do("POST", f"{tok.surl}/pows/check", check, h)
            if st == 400:
                raise SessionSolveError(f"pows/check 400: {clip(resp, 180)}")
            if st != 200:
                raise SessionSolveError(f"pows/check {st}: {clip(resp, 180)}")
            try:
                chk = json.loads(resp)
            except Exception as e:
                raise SessionSolveError(f"pows/check json: {clip(resp, 180)}") from e
            action = str(chk.get("action") or "")
            if action in ("challenge", "pass"):
                return
            if action == "next":
                if chk.get("work_config"):
                    work = chk["work_config"]
                if chk.get("pow_token"):
                    pow_token = str(chk["pow_token"])
                continue
            raise SessionSolveError(f"pows/check unexpected action {action!r}")
        raise SessionSolveError("pows/check too many rounds")

    def _post_fc_a(
        self, http: ArkoseHTTP, tok: ArkoseToken, game: dict[str, Any],
        enf: str, referer: str, category: str, action: str, with_xrid: bool,
    ) -> None:
        session_token = str(game.get("session_token") or "")
        challenge_id = str(game.get("challengeID") or "")
        game_type = str((game.get("game_data") or {}).get("gameType") or "")
        pairs = [
            "sid", tok.sid,
            "session_token", session_token,
            "analytics_tier", tok.at,
            "disableCookies", "false",
        ]
        if category != "Site URL":
            pairs += ["game_token", challenge_id, "game_type", game_type]
        pairs += [
            "render_type", "canvas",
            "is_compatibility_mode", "false",
            "category", category,
            "action", action,
        ]
        h = arkose_headers(tok.surl, referer)
        h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        h["X-Requested-With"] = "XMLHttpRequest"
        h["X-Newrelic-Timestamp"] = newrelic_ts()
        if with_xrid:
            try:
                h["X-Requested-Id"] = encrypt_arkose("{}", "REQUESTED" + session_token + "ID")
            except Exception:
                pass
        http.do("POST", f"{tok.surl}/fc/a/", form_encode(*pairs), h)


class _PowSetup400(SessionSolveError):
    pass


def _ca_next_images(c: dict[str, Any]) -> list[str]:
    imgs = list(c.get("_challenge_imgs") or [])
    if not imgs:
        rc = c.get("round_config") or {}
        img = rc.get("challenge_image") if isinstance(rc, dict) else ""
        if img:
            imgs = [str(img)]
    return [str(x) for x in imgs if x]


def _ca_unsolved(c: dict[str, Any], detail: str) -> str:
    if c.get("response") == "answered" and not c.get("solved"):
        return f"session-solve: answered but not solved {detail}"
    return f"session-solve: not solved {detail}"


def _b64(s: str) -> str:
    import base64

    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def solve_session(
    *,
    api_key: str,
    website_url: str,
    blob: str,
    user_agent: str = "",
    proxy_url: str = "",
    public_key: str = SIGNUP_PUBLIC_KEY,
    surl: str = SIGNUP_SURL,
    log: LogFn | None = None,
    harvest_fn: Callable[..., HarvestSeed] | None = None,
    solver: SessionSolver | None = None,
) -> SessionResult:
    lf = log if callable(log) else (lambda _m: None)
    if not api_key:
        raise SessionSolveError("yescaptcha 未配置 API Key")
    if not blob:
        raise SessionSolveError("captcha_required 但没有 x-ims-captcha-encrypted blob")
    harvester = harvest_fn or harvest_gt2
    seed = harvester(
        website_url=website_url,
        blob=blob,
        public_key=public_key or SIGNUP_PUBLIC_KEY,
        surl=surl or SIGNUP_SURL,
        proxy_url=proxy_url,
        user_agent=user_agent,
        log=lf,
    )
    lf(
        f"gt2 harvested suppressed={seed.suppressed} token_len={len(seed.token)} "
        f"arid={bool(seed.arid)}"
    )
    if seed.suppressed or "sup=1" in (seed.token or ""):
        seed.suppressed = True
        return SessionResult(token=seed.token, cookies=seed.cookies, suppressed=True)
    sess = solver or SessionSolver(
        api_key=api_key, proxy_url=proxy_url,
        user_agent=seed.user_agent or user_agent, log=lf,
    )
    return sess.continue_session(seed, public_key=public_key, surl=surl)


def not_retryable(err: BaseException) -> bool:
    if isinstance(err, UnknownQuestion):
        return True
    msg = str(err).lower().replace("_", " ")
    for stop in (
        "zero balance",
        "insufficient",
        "no balance",
        "out of credit",
        "key does not exist",
        "invalid api key",
        "unauthorized",
        "captcha question type unsupported",
    ):
        if stop in msg:
            return True
    return False


def is_navigation_failed(err: BaseException) -> bool:
    if isinstance(err, NavigationFailed):
        return True
    msg = str(err).lower()
    return any(
        n in msg
        for n in (
            "page.goto",
            "err_connection",
            "err_proxy",
            "err_tunnel_connection_failed",
            "err_name_not_resolved",
            "err_timed_out",
            "net::err",
        )
    )


def is_unknown_question(err: BaseException) -> bool:
    return isinstance(err, UnknownQuestion) or "ERROR_UNKNOWN_QUESTION" in str(err)
