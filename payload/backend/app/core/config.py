from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "okad 管理平台"
    API_PREFIX: str = "/api"

    # 安全配置:生产环境务必通过 .env 覆盖 SECRET_KEY
    SECRET_KEY: str = "change-me-in-production-please-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # SQLite 数据库文件
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'app.db'}"

    # 跨域允许的前端地址
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 默认管理员账号(首次初始化时创建)
    FIRST_ADMIN_USERNAME: str = "admin"
    FIRST_ADMIN_PASSWORD: str = "CHANGE_ME"
    FIRST_ADMIN_NICKNAME: str = "超级管理员"


settings = Settings()
