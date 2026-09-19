"""Synthetic mouse bio for /fc/ca/ (adAuto internal/captcha/bio.go)."""

from __future__ import annotations

import base64
import json
import random


def gen_mouse_segment(t_start: int) -> tuple[str, int]:
    n_clicks = 3 + random.randint(0, 3)
    x0 = 40 + random.random() * 90
    y0 = 60 + random.random() * 110
    t = t_start
    parts: list[str] = []
    for _ in range(n_clicks):
        tx = 70 + random.random() * 270
        ty = 110 + random.random() * 210
        cx = (x0 + tx) / 2 + (random.random() * 140 - 70)
        cy = (y0 + ty) / 2 + (random.random() * 140 - 70)
        n_moves = 12 + random.randint(0, 18)
        for i in range(n_moves + 1):
            p = i / n_moves
            ease = p * p * (3 - 2 * p)
            inv = 1 - ease
            bx = inv * inv * x0 + 2 * inv * ease * cx + ease * ease * tx
            by = inv * inv * y0 + 2 * inv * ease * cy + ease * ease * ty
            jx = bx + (random.random() * 3.6 - 1.8)
            jy = by + (random.random() * 3.6 - 1.8)
            parts.append(f"{t},0,{int(round(jx))},{int(round(jy))};")
            dt = 8 + random.randint(0, 37)
            if random.random() < 0.12:
                dt += 30 + random.randint(0, 100)
            t += dt
        t += 40 + random.randint(0, 120)
        fx, fy = int(round(tx)), int(round(ty))
        parts.append(f"{t},1,{fx},{fy};")
        t += 45 + random.randint(0, 70)
        parts.append(f"{t},2,{fx},{fy};")
        t += 80 + random.randint(0, 270)
        x0, y0 = float(fx), float(fy)
    return "".join(parts), t


def build_bio_payload(mbio: str) -> str:
    raw = json.dumps({"mbio": mbio, "tbio": "", "kbio": ""}, separators=(",", ":"))
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")
