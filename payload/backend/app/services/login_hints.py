"""Private, opt-in login hints. Plaintext credentials stay outside source and static assets."""
import json
from pathlib import Path
import tempfile

from sqlalchemy import select

from app.core.config import BASE_DIR
from app.core.security import verify_password
from app.models.user import User
from app.db.session import engine

HINTS_PATH = (Path("/app/data/.local/login-hints.json") if Path("/app/data").is_dir()
              else BASE_DIR / ".local/login-hints.json")


def read_config() -> dict:
    try:
        config = json.loads(HINTS_PATH.read_text(encoding="utf-8"))
        return config if isinstance(config, dict) else {}
    except (OSError, ValueError):
        return {}


def public_local_request(request, config: dict) -> bool:
    return (config.get("public_on_loopback") is True
            and config.get("current_environment") == "local"
            and request.url.hostname in ("localhost", "127.0.0.1", "::1")
            and request.client is not None
            and request.client.host in ("127.0.0.1", "::1"))


def entries(db, config: dict) -> list[dict]:
    result = []
    for source in config.get("entries") or []:
        if not isinstance(source, dict) or source.get("environment") not in ("local", "online"):
            continue
        entry = {key: str(source.get(key) or "") for key in ("environment", "label", "url", "username", "password")}
        if entry["environment"] == config.get("current_environment"):
            user = db.scalar(select(User).where(User.username == entry["username"]))
            try:
                valid = user and user.is_active and user.is_superuser and verify_password(entry["password"], user.hashed_password)
            except (ValueError, TypeError):
                valid = False
            if not valid:
                entry["password"] = ""
                entry["message"] = "密码已变更或账号不可用，请重新登记"
        result.append(entry)
    return result


def password_changed(username: str, password: str, *, db) -> None:
    """Refresh an existing hint after a successful password change; never opt in automatically."""
    # Only the application's configured database owns its private hints file.
    # Isolated tests or maintenance sessions must not rewrite real credentials.
    if db.get_bind() is not engine:
        return
    config = read_config()
    changed = False
    for entry in config.get("entries") or []:
        if entry.get("environment") == config.get("current_environment") and entry.get("username") == username:
            entry["password"] = password
            changed = True
    if not changed:
        return
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=HINTS_PATH.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(config, handle, ensure_ascii=False, indent=2)
        temporary.chmod(0o600)
        temporary.replace(HINTS_PATH)
    except OSError:
        # A read-only hints file must not cause a successful password change to fail.
        from app.services.log_store import STORE
        STORE.add("WARNING", "login_hints", "登录密码已修改，密码提示未能更新，请重新登记")
