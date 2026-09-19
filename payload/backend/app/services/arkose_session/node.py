"""Node sidecars for Arkose PoW sequence + dapib tguess."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.services.arkose_session.util import clip


class NodeError(RuntimeError):
    pass


def script_dir() -> Path:
    for key in ("ADOBE_ARKOSE_SESSION_DIR", "ADREG_ARKOSE_SESSION_DIR"):
        v = (os.environ.get(key) or "").strip()
        if v:
            return Path(v)
    return Path(__file__).resolve().parents[3] / "tools" / "arkose-session"


def node_bin() -> str:
    return (
        (os.environ.get("ADOBE_ARKOSE_NODE") or "").strip()
        or (os.environ.get("ADREG_ARKOSE_NODE") or "").strip()
        or "node"
    )


def ensure_runner(name: str) -> Path:
    bin_name = node_bin()
    if not shutil.which(bin_name):
        raise NodeError(f"node not found ({bin_name}); Arkose session-solve needs Node for PoW/tguess")
    runner = script_dir() / name
    if not runner.is_file():
        raise NodeError(f"{name} missing at {runner}")
    return runner


def run_node(args: list[str], stdin: bytes | None = None, timeout: float = 45) -> bytes:
    bin_name = node_bin()
    try:
        proc = subprocess.run(
            [bin_name, *args],
            input=stdin,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise NodeError(f"node timeout: {clip(e.stderr or b'', 240)}") from e
    except FileNotFoundError as e:
        raise NodeError(f"node not found ({bin_name})") from e
    if proc.returncode != 0:
        raise NodeError(
            f"node exit {proc.returncode}: {clip(proc.stderr, 240) or clip(proc.stdout, 240)}"
        )
    return proc.stdout


def run_pow(seq_js: bytes, work: dict[str, Any], timeout_ms: int = 30000) -> dict[str, Any]:
    runner = ensure_runner("pow_runner.js")
    with tempfile.TemporaryDirectory(prefix="okad-pow-") as tmp:
        seq_path = Path(tmp) / "sequence.js"
        seq_path.write_bytes(seq_js)
        req: dict[str, Any] = {
            "seed": work.get("seed"),
            "starting_nonce": work.get("starting_nonce") or 0,
            "timeout": timeout_ms,
        }
        if "splits" in work:
            req["splits"] = work["splits"]
        if "count" in work:
            req["count"] = work["count"]
        raw = run_node(
            [str(runner), str(seq_path)],
            stdin=json.dumps(req).encode("utf-8"),
            timeout=timeout_ms / 1000 + 15,
        )
    try:
        sol = json.loads(raw)
    except Exception as e:
        raise NodeError(f"pow_runner json: {clip(raw, 200)}") from e
    if not isinstance(sol, dict) or sol.get("transform") is None:
        raise NodeError(f"pow_runner empty transform: {clip(raw, 200)}")
    return sol


def run_tguess(session_token: str, guess_json: str, dapib: str) -> str:
    if not (dapib or "").strip():
        return ""
    runner = ensure_runner("tguess_runner.js")
    with tempfile.TemporaryDirectory(prefix="okad-tguess-") as tmp:
        dapib_path = Path(tmp) / "dapib.js"
        dapib_path.write_text(dapib, encoding="utf-8")
        raw = run_node(
            [str(runner), session_token, guess_json, str(dapib_path)],
            timeout=15,
        )
    return raw.decode("utf-8", "replace").strip()
