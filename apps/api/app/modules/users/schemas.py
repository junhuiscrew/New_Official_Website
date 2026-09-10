"""Users 与 RBAC Admin API 模型。"""

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """创建后台用户请求。"""

    email: EmailStr
    password: str = Field(min_length=12, max_length=1024)
    display_name: str | None = Field(default=None, max_length=100)
    role_names: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    """更新后台用户基础信息请求。"""

    display_name: str | None = Field(default=None, max_length=100)


class UserData(BaseModel):
    """不包含密码的后台用户输出。"""

    id: str
    email: str
    display_name: str | None
    is_active: bool
    roles: list[str]


class PermissionData(BaseModel):
    """原子权限输出。"""

    id: str
    code: str
    display_name: str


class RoleData(BaseModel):
    """角色及其权限矩阵输出。"""

    id: str
    name: str
    display_name: str
    description: str | None
    is_system: bool
    permissions: list[str]


class RolePermissionUpdate(BaseModel):
    """显式替换角色权限请求。"""

    permission_codes: list[str]
