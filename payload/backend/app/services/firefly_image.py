"""Firefly 3P 出图测试(纯 API,参考 adobe2api 协议)。

用子号的 firefly access_token 调:credits/cost 预检 → 3p-images/generate-async →
轮询结果,拿到图片地址。用于号池"测试出图"功能,验证账号能否正常生成图片。

认证:Authorization: Bearer <IMS token> + X-api-key: clio-playground-web +
x-nonce = sha256(f"{userId}-{prompt[:256]}")。
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import uuid
from typing import Any, Callable, Optional

from app.services.firefly import _new_session, extract_account_id

LogFn = Callable[[str], None]

API_KEY = "clio-playground-web"
SUBMIT_URL = "https://firefly-3p.ff.adobe.io/v2/3p-images/generate-async"
COST_URL = "https://bks.adobe.io/v2/credits/cost"
_ORIGIN = "https://firefly.adobe.com"

# 2K 各比例尺寸(取自参考协议,gemini-flash/nano-banana 用)
_SIZE_2K = {
    "1:1": {"width": 2048, "height": 2048},
    "16:9": {"width": 2752, "height": 1536},
    "9:16": {"width": 1536, "height": 2752},
    "4:3": {"width": 2400, "height": 1792},
    "3:4": {"width": 1792, "height": 2400},
    "21:9": {"width": 3168, "height": 1344},
    "3:2": {"width": 2528, "height": 1696},
}

# gpt-image v2 仅支持这几种固定尺寸,其余走 modelSpecificPayload.size=auto
_GPT_IMAGE_SIZE = {
    "3:2": {"width": 1536, "height": 1024},
    "1:1": {"width": 1024, "height": 1024},
    "2:3": {"width": 1024, "height": 1536},
}

# 模型 → 计费 feature id
_COST_FEATURE: dict[tuple[str, str], str] = {
    ("gemini-flash", "nano-banana-3"): "firefly_3p:external:nano_banana_3",
    ("gemini-flash", "nano-banana-2"): "firefly_3p:external:gemini_flash_2",
    ("gpt-image", "2"): "firefly_3p:external:gpt_image_2",
}


def _mklog(log: Optional[LogFn]) -> LogFn:
    return log if callable(log) else (lambda _m: None)


def _nonce(token: str, prompt: str) -> str:
    sub = extract_account_id(token)
    if not sub:
        return ""
    return hashlib.sha256(f"{sub}-{prompt[:256]}".encode("utf-8")).hexdigest()


def gen_arp_session_id() -> str:
    """生成 x-arp-session-id(Adobe 反爬头)。

    实测:该头只要存在且为合法 base64({"sid","ftr"}) 即可通过,ftr 无需真实
    (不带此头时 Adobe 会伪装返回 408 "system under load")。
    """
    ms = int(time.time() * 1000)
    ftr = (
        f"{secrets.token_hex(16)}_{ms}__"
        f"{secrets.token_urlsafe(9)}_{secrets.token_urlsafe(4)}="
        f"-{secrets.randbelow(9000) + 1000}-v2_tt"
    )
    raw = json.dumps({"sid": str(uuid.uuid4()), "ftr": ftr})
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def _browser_headers() -> dict[str, str]:
    return {
        "origin": _ORIGIN,
        "referer": _ORIGIN + "/",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "sec-fetch-site": "cross-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
    }


def _submit_headers(token: str, prompt: str, arp_session_id: str = "") -> dict[str, str]:
    h = _browser_headers()
    h.update({
        "Authorization": f"Bearer {token}",
        "x-api-key": API_KEY,
        "content-type": "application/json",
        "accept": "*/*",
        "x-arp-session-id": (arp_session_id or "").strip() or gen_arp_session_id(),
    })
    nonce = _nonce(token, prompt)
    if nonce:
        h["x-nonce"] = nonce
    return h


def _poll_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "accept": "*/*",
        "referer": _ORIGIN + "/",
        "origin": _ORIGIN,
    }


def _build_payload(
    prompt: str,
    aspect_ratio: str,
    model_id: str,
    model_version: str,
    *,
    quality: str = "medium",
    width: int | None = None,
    height: int | None = None,
) -> dict:
    seed = int(time.time()) % 999999

    # GPT Image 2(img2):payload 形态与 nano-banana 不同。
    # 实测:顶层 size={width,height} 会被真实采纳(如 2048x2048);
    #       modelSpecificPayload.quality 控制质量(low/medium/high)。
    if model_id == "gpt-image" and str(model_version) == "2":
        payload = {
            "n": 1,
            "seeds": [seed],
            "output": {"storeInputs": True},
            "prompt": prompt,
            "referenceBlobs": [],
            "modelId": "gpt-image",
            "modelVersion": "2",
            "generationMetadata": {"module": "text2image", "submodule": "ff-image-generate"},
            "generationSettings": {"detailLevel": 3},
            "modelSpecificPayload": {"quality": quality},
        }
        if width and height:
            payload["size"] = {"width": int(width), "height": int(height)}
        else:
            fixed = _GPT_IMAGE_SIZE.get(aspect_ratio)
            if fixed:
                payload["size"] = fixed
            else:
                payload["modelSpecificPayload"]["size"] = "auto"
        return payload

    # gemini-flash / nano-banana
    if width and height:
        size = {"width": int(width), "height": int(height)}
    else:
        size = _SIZE_2K.get(aspect_ratio, _SIZE_2K["16:9"])
    return {
        "modelId": model_id,
        "modelVersion": model_version,
        "n": 1,
        "prompt": prompt,
        "size": size,
        "seeds": [seed],
        "groundSearch": False,
        "output": {"storeInputs": True},
        "generationMetadata": {"module": "text2image", "submodule": "ff-image-generate"},
        "modelSpecificPayload": {"parameters": {"addWatermark": False}},
        "referenceBlobs": [],
    }


def _cost_metadata(model_id: str, quality: str) -> dict:
    if model_id == "gpt-image":
        return {"quality": quality, "enableCreditType": True}
    return {"imageResolution": "2K", "enableCreditType": True}


def test_generate(
    *,
    access_token: str,
    arp_session_id: str = "",
    prompt: str = "a cute corgi puppy running on a sunny beach, cinematic",
    proxy_url: str = "",
    aspect_ratio: str = "1:1",
    model_id: str = "gpt-image",
    model_version: str = "2",
    quality: str = "medium",
    width: int | None = 2048,
    height: int | None = 2048,
    timeout: int = 120,
    log: Optional[LogFn] = None,
) -> dict[str, Any]:
    """返回 {success, message, image_url, prompt}。"""
    lf = _mklog(log)
    if not access_token:
        return {"success": False, "message": "缺少 access_token,请先批量登录刷新", "image_url": ""}

    sess = _new_session(proxy_url)
    try:
        # 计费预检(best-effort,不阻断)
        feature = _COST_FEATURE.get((model_id, str(model_version)))
        if feature:
            try:
                sess.post(
                    COST_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "x-api-key": API_KEY,
                        "content-type": "application/json",
                        "accept": "*/*",
                    },
                    json={"features": {feature: 1},
                          "metadata": _cost_metadata(model_id, quality)},
                )
            except Exception:
                pass

        payload = _build_payload(
            prompt, aspect_ratio, model_id, model_version,
            quality=quality, width=width, height=height,
        )
        size_desc = f"{width}x{height}" if (width and height) else aspect_ratio
        lf(f"提交出图任务(模型 {model_id}/{model_version}, {quality}, {size_desc})…")

        # Adobe 偶发过载会返回 408/429/5xx(system under load),做退避重试
        _TRANSIENT = {408, 425, 429, 500, 502, 503, 504}
        max_attempts = 4
        r = None
        for attempt in range(1, max_attempts + 1):
            r = sess.post(
                SUBMIT_URL,
                headers=_submit_headers(access_token, prompt, arp_session_id),
                json=payload,
            )
            if r.status_code not in _TRANSIENT:
                break
            if attempt < max_attempts:
                wait = min(2 ** attempt, 8)
                lf(f"Adobe 服务繁忙({r.status_code}),{wait}s 后重试({attempt}/{max_attempts - 1})…")
                time.sleep(wait)

        if r is None:
            return {"success": False, "message": "提交失败:无响应", "image_url": ""}
        if r.status_code in (401, 403):
            access_error = r.headers.get("x-access-error") or ""
            if "taste_exhausted" in access_error:
                return {"success": False, "message": "额度已耗尽(taste_exhausted)", "image_url": ""}
            return {"success": False, "message": f"token 失效或无权限({r.status_code})", "image_url": ""}
        if r.status_code in _TRANSIENT:
            return {"success": False,
                    "message": f"Adobe 服务繁忙,稍后再试({r.status_code} system under load)",
                    "image_url": ""}
        if r.status_code != 200:
            return {"success": False,
                    "message": f"提交失败 {r.status_code}: {(r.text or '')[:200]}",
                    "image_url": ""}

        try:
            data = r.json()
        except Exception:
            data = {}
        poll_url = r.headers.get("x-override-status-link") or (
            ((data.get("links") or {}).get("result") or {}).get("href")
        )
        if not poll_url:
            return {"success": False, "message": "提交成功但未返回轮询地址", "image_url": ""}

        lf("已提交,等待出图 …")
        start = time.time()
        # 首轮按提交响应的 retry-after 等待
        try:
            sleep_s = float(r.headers.get("retry-after") or 3)
        except Exception:
            sleep_s = 3.0
        while time.time() - start < timeout:
            time.sleep(max(2.0, min(sleep_s, 8.0)))
            pr = sess.get(poll_url, headers=_poll_headers(access_token))
            if pr.status_code != 200:
                if pr.status_code in (401, 403):
                    return {"success": False, "message": "轮询时 token 失效", "image_url": ""}
                continue
            # Adobe 每次轮询都会回新的状态地址,跟随它
            poll_url = pr.headers.get("x-override-status-link") or poll_url
            try:
                sleep_s = float(pr.headers.get("retry-after") or sleep_s)
            except Exception:
                pass
            try:
                latest = pr.json()
            except Exception:
                continue
            outputs = latest.get("outputs") or []
            if outputs:
                image_url = ((outputs[0] or {}).get("image") or {}).get("presignedUrl") or ""
                if image_url:
                    lf("✓ 出图成功")
                    return {"success": True, "message": "出图成功", "image_url": image_url,
                            "prompt": prompt}
                return {"success": False, "message": "任务完成但无图片地址", "image_url": ""}
            status_val = str(latest.get("status") or "").upper()
            if status_val in {"FAILED", "CANCELLED", "ERROR"}:
                return {"success": False, "message": f"出图失败:{str(latest)[:200]}", "image_url": ""}

        return {"success": False, "message": f"出图超时({timeout}s)", "image_url": ""}
    finally:
        try:
            sess.close()
        except Exception:
            pass
