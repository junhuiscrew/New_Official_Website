"""Authentication API 请求与响应模型。"""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """登录请求。"""

    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class CurrentUserData(BaseModel):
    """Admin 当前用户的安全公开字段与授权集合。"""

    id: str
    email: str
    display_name: str | None
    roles: list[str]
    permissions: list[str]


class LogoutData(BaseModel):
    """退出响应。"""

    revoked: bool
