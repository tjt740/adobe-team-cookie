"""YesCaptcha FunCaptchaClassification (adAuto yesclassify.go).

Workers only see the image. Do not put websitePublicKey / blob / proxy in the task.
objects[0] is used as-is (official 0-based). Do not subtract one.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any, Callable

import requests

from app.services.arkose_session.questions import (
    classification_question,
    yes_question_known,
)
from app.services.arkose_session.util import clip, worker_proxy

YES_API_DEFAULT = "https://api.yescaptcha.com"
YES_BUSY_ATTEMPTS = 5
YES_BUSY_DELAYS = [1.0, 2.0, 3.0, 6.0]
YES_CLASSIFICATION_POINTS = 3
YES_POINTS_PER_RMB = 1020

LogFn = Callable[[str], None]


class ClassifyError(RuntimeError):
    pass


class UnknownQuestion(ClassifyError):
    """Vendor has no model for this variant. A new harvest gets the same type."""


def yes_api_base() -> str:
    for key in ("ADOBE_YESCAPTCHA_API", "ADREG_YESCAPTCHA_API", "YESCAPTCHA_API"):
        v = (os.environ.get(key) or "").strip()
        if v:
            return v.rstrip("/")
    return YES_API_DEFAULT


def classification_payload(img: bytes, question: str) -> dict[str, Any]:
    return {
        "type": "FunCaptchaClassification",
        "image": base64.b64encode(img).decode("ascii"),
        "question": question,
    }


def parse_click_field(raw: Any) -> list[int] | None:
    if raw is None:
        return None
    if isinstance(raw, int) and not isinstance(raw, bool):
        return [raw]
    if isinstance(raw, float):
        return [int(raw)]
    if isinstance(raw, str) and raw.strip():
        try:
            return [int(raw.strip())]
        except ValueError:
            return None
    if isinstance(raw, list) and raw:
        out: list[int] = []
        for v in raw:
            if isinstance(v, bool):
                return None
            if isinstance(v, int):
                out.append(v)
            elif isinstance(v, float):
                out.append(int(v))
            elif isinstance(v, str):
                try:
                    out.append(int(v.strip()))
                except ValueError:
                    return None
            else:
                return None
        return out
    return None


def parse_classification_solution(sol: Any) -> list[int]:
    if not sol:
        raise ClassifyError("empty classification solution")
    if isinstance(sol, str):
        try:
            sol = json.loads(sol)
        except Exception as e:
            raise ClassifyError(f"classification solution: {e}") from e
    if not isinstance(sol, dict):
        raise ClassifyError("classification solution missing objects")
    objects = parse_click_field(sol.get("objects"))
    if objects:
        return objects
    if sol.get("token"):
        raise ClassifyError("classification solution has token, not objects (wrong task type)")
    raise ClassifyError("classification solution missing objects")


def wave_index(clicks: list[int]) -> int:
    if not clicks:
        raise ClassifyError("empty click")
    return clicks[0]


def is_yes_busy(err: BaseException) -> bool:
    s = str(err)
    for n in (
        "ERROR_SERVICE_UNAVAILABLE",
        "ERROR_RATE_LIMIT",
        "ERROR_NO_SLOT_AVAILABLE",
        "繁忙",
        "服务暂时不可用",
    ):
        if n in s:
            return True
    return False


def is_unknown_question_code(code: str, desc: str) -> bool:
    return "ERROR_UNKNOWN_QUESTION" in (code or "") or "ERROR_UNKNOWN_QUESTION" in (desc or "")


def _task_api_error(op: str, code: str, desc: str) -> ClassifyError:
    msg = " ".join(p for p in (code, desc) if p) or "unknown error"
    if is_unknown_question_code(code, desc):
        return UnknownQuestion(f"{op}: {msg}")
    return ClassifyError(f"{op}: {msg}")


def _api_proxies(proxy_url: str) -> dict[str, str] | None:
    override = (os.environ.get("ADOBE_CAPTCHA_API_PROXY") or "").strip()
    if override.lower() in ("direct", "off", "none"):
        return None
    if override:
        p = worker_proxy(override)
    else:
        p = worker_proxy(proxy_url)
    if not p:
        return None
    return {"http": p, "https": p}


def create_and_poll_solution(
    api_base: str,
    client_key: str,
    task: dict[str, Any],
    *,
    proxy_url: str = "",
    timeout: int = 180,
) -> tuple[Any, Any]:
    sess = requests.Session()
    sess.trust_env = False
    proxies = _api_proxies(proxy_url)
    try:
        cr = sess.post(
            f"{api_base.rstrip('/')}/createTask",
            json={"clientKey": client_key, "task": task},
            proxies=proxies,
            timeout=30,
        )
        body = _json(cr)
        if int(body.get("errorId") or 0) != 0:
            raise _task_api_error(
                "createTask",
                str(body.get("errorCode") or ""),
                str(body.get("errorDescription") or cr.text[:180]),
            )
        task_id = body.get("taskId")
        sol = body.get("solution")
        if body.get("status") == "ready" and sol:
            return sol, task_id
        if task_id in (None, ""):
            raise ClassifyError(f"createTask 未返回 taskId: {clip(cr.text, 180)}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(3)
            pr = sess.post(
                f"{api_base.rstrip('/')}/getTaskResult",
                json={"clientKey": client_key, "taskId": task_id},
                proxies=proxies,
                timeout=30,
            )
            pb = _json(pr)
            if int(pb.get("errorId") or 0) != 0:
                raise _task_api_error(
                    "getTaskResult",
                    str(pb.get("errorCode") or ""),
                    str(pb.get("errorDescription") or pr.text[:180]),
                )
            sol = pb.get("solution")
            if pb.get("status") == "ready" and sol:
                return sol, task_id
        raise ClassifyError("captcha timeout")
    finally:
        sess.close()


def classify_yes_wave(
    *,
    api_key: str,
    img: bytes,
    instruction: str,
    game_variant: str,
    tiles: int,
    rotate: bool,
    proxy_url: str = "",
    log: LogFn | None = None,
    poll: Callable[..., tuple[Any, Any]] | None = None,
) -> tuple[int, Any]:
    lf = log if callable(log) else (lambda _m: None)
    if not api_key:
        raise ClassifyError("arkose-session: missing yescaptcha key")
    question = classification_question(instruction, game_variant)
    if not yes_question_known(question):
        lf(
            f"session-solve classify=yescaptcha skip unknown-question "
            f"variant={clip(game_variant or instruction, 40)} question={clip(question, 80)}"
        )
        raise UnknownQuestion(clip(question, 80))
    payload = classification_payload(img, question)
    if "websitePublicKey" in payload:
        raise ClassifyError("FunCaptchaClassification must not include websitePublicKey")
    lf(
        f"session-solve image classify=yescaptcha question={clip(question, 120)} "
        f"tiles={tiles} rotate={rotate}"
    )
    create_poll = poll or (
        lambda api_base, key, task: create_and_poll_solution(
            api_base, key, task, proxy_url=proxy_url
        )
    )
    err: Exception | None = None
    sol: Any = None
    task_id: Any = None
    for attempt in range(YES_BUSY_ATTEMPTS):
        if attempt > 0:
            time.sleep(YES_BUSY_DELAYS[min(attempt - 1, len(YES_BUSY_DELAYS) - 1)])
        try:
            sol, task_id = create_poll(yes_api_base(), api_key, payload)
            err = None
            break
        except Exception as e:  # noqa: BLE001
            err = e
            if not is_yes_busy(e):
                raise
            lf(f"session-solve yescaptcha busy attempt={attempt + 1}/{YES_BUSY_ATTEMPTS}: {e}")
    if err is not None:
        raise err
    objects = parse_classification_solution(sol)
    idx = wave_index(objects)
    lf(
        f"session-solve classify=yescaptcha objects={objects} index={idx} "
        f"tiles={tiles} taskId={task_id} points={YES_CLASSIFICATION_POINTS}"
    )
    if rotate:
        return idx, task_id
    if tiles > 0 and (idx < 0 or idx >= tiles):
        raise ClassifyError(
            f"yescaptcha objects={objects} index={idx} out of range tiles={tiles}"
        )
    return idx, task_id


def _json(resp: Any) -> dict[str, Any]:
    try:
        data = resp.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
