import re

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, field_validator


class PasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: SecretStr

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw) < 10 or len(raw.encode("utf-8")) > 72:
            raise ValueError("密码至少 10 个字符，且不超过 72 字节")
        return value


class AdminCreate(PasswordInput):
    username: str = Field(min_length=3, max_length=50)
    nickname: str = Field(default="", max_length=50)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", value):
            raise ValueError("用户名须为 3～50 位字母、数字、点、下划线或短横线")
        return value


class AdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str | None = Field(default=None, max_length=50)
    is_active: StrictBool | None = None

    @field_validator("nickname", "is_active")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("不能设为空值")
        return value
