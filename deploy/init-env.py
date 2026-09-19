"""Create production credentials once; never replace existing configuration."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
env = root / ".env"
if not env.exists():
    content = "\n".join([
        "SECRET_KEY=" + secrets.token_urlsafe(48),
        "FIRST_ADMIN_USERNAME=admin",
        "FIRST_ADMIN_PASSWORD=" + secrets.token_urlsafe(24),
        "FIRST_ADMIN_NICKNAME=超级管理员",
        "CORS_ORIGINS=[]",
        "ACCESS_TOKEN_EXPIRE_MINUTES=1440",
        "",
    ])
    with env.open("x", encoding="utf-8") as output:
        env.chmod(0o600)
        output.write(content)
    print("Created .env with random credentials.")
else:
    print("Preserved existing .env.")
(root / "data").mkdir(exist_ok=True, mode=0o700)
