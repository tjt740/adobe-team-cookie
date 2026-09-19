"""Arkose EVP_BytesToKey AES-256-CBC (adAuto internal/captcha/crypt.go)."""

from __future__ import annotations

import json
import os
from hashlib import md5
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


def encrypt_arkose(plaintext: str, key: str) -> str:
    salt = bytes(ord("a") + (b % 26) for b in os.urandom(8))
    return encrypt_arkose_with_salt(plaintext, key, salt)


def encrypt_arkose_with_salt(plaintext: str, key: str, salt: bytes) -> str:
    if len(salt) != 8:
        raise ValueError("arkose salt must be 8 bytes")
    aes_key, iv = _key_iv(key, salt)
    padder = PKCS7(128).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    encryptor = Cipher(algorithms.AES(aes_key), modes.CBC(iv)).encryptor()
    ct = encryptor.update(padded) + encryptor.finalize()
    out = json.dumps(
        {"ct": _b64(ct), "iv": iv.hex(), "s": salt.hex()},
        separators=(",", ":"),
    )
    if " " in out:
        raise ValueError("arkose cipher JSON must be compact")
    return out


def decrypt_arkose(blob: str, key: str) -> str:
    obj = json.loads(blob)
    salt = bytes.fromhex(obj["s"])
    aes_key, iv = _key_iv(key, salt)
    raw = _b64d(obj["ct"])
    decryptor = Cipher(algorithms.AES(aes_key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(raw) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    pt = unpadder.update(padded) + unpadder.finalize()
    return pt.decode("utf-8")


def compact_json(v: Any) -> str:
    out = json.dumps(v, separators=(",", ":"), ensure_ascii=False)
    if " " in out:
        raise ValueError("json not compact")
    return out


def is_image_magic(raw: bytes) -> bool:
    return (
        raw.startswith(b"\xff\xd8")
        or raw.startswith(b"\x89PNG")
        or raw.startswith(b"GIF8")
        or raw.startswith(b"RIFF")
    )


def decrypt_challenge_image(raw: bytes, key: str) -> bytes:
    if is_image_magic(raw):
        return raw
    try:
        obj = json.loads(raw)
    except Exception as e:
        raise ValueError(f"challenge image json: {e}") from e
    if not key:
        raise ValueError("encrypted challenge image without decryption_key")
    if not isinstance(obj, dict):
        raise ValueError("encrypted challenge image not an object")
    ct = _first_str(obj, "data", "ct", "cipher", "payload")
    ivs = _first_str(obj, "iv")
    if not ct:
        raise ValueError("encrypted challenge image missing ciphertext")
    ctb = _decode_key_bytes(ct)
    kb = _decode_key_bytes(key)
    if len(kb) not in (16, 24, 32):
        kb = md5(kb).digest()
    iv = _decode_key_bytes(ivs) if ivs else b""
    if len(iv) != 16:
        if len(ctb) > 16:
            iv, ctb = ctb[:16], ctb[16:]
        else:
            raise ValueError("encrypted image bad iv")
    if len(ctb) % 16 != 0:
        raise ValueError("encrypted image bad ciphertext")
    decryptor = Cipher(algorithms.AES(kb), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ctb) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    pt = unpadder.update(padded) + unpadder.finalize()
    if not is_image_magic(pt):
        raise ValueError("decrypted challenge image is not jpeg/png")
    return pt


def _key_iv(key: str, salt: bytes) -> tuple[bytes, bytes]:
    dx = b""
    salted = ""
    for _ in range(3):
        dx = md5(dx + key.encode("utf-8") + salt).digest()
        salted += dx.hex()
    if len(salted) < 96:
        raise ValueError("arkose key material short")
    return bytes.fromhex(salted[:64]), bytes.fromhex(salted[64:96])


def _first_str(m: dict, *keys: str) -> str:
    for k in keys:
        v = m.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def _decode_key_bytes(s: str) -> bytes:
    try:
        b = bytes.fromhex(s)
        if b:
            return b
    except ValueError:
        pass
    try:
        import base64

        b = base64.b64decode(s)
        if b:
            return b
    except Exception:
        pass
    return s.encode("utf-8")


def _b64(raw: bytes) -> str:
    import base64

    return base64.b64encode(raw).decode("ascii")


def _b64d(s: str) -> bytes:
    import base64

    return base64.b64decode(s)
