"""用户、角色、权限及其显式关联表模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin


class CaseInsensitiveEmail(TypeDecorator[str]):
    """
    在 PostgreSQL 使用 CITEXT，在轻量测试数据库回退到 VARCHAR。

    输入：数据库 dialect。

    输出：对应 dialect 的邮箱字段类型。
    """

    impl = String(320)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        """
        为目标数据库选择大小写不敏感邮箱类型。

        输入：
            dialect: Dialect，SQLAlchemy 当前数据库方言。

        输出：TypeEngine，PostgreSQL 为 CITEXT，其余为 VARCHAR(320)。
        """
        if dialect.name == "postgresql":
            return dialect.type_descriptor(CITEXT())
        return dialect.type_descriptor(String(320))


class User(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """
    表示可进入管理系统的用户账户。

    输入：email、password_hash 等账户字段。

    输出：User ORM 实体，可通过 user_roles 关联角色。
    """

    __tablename__ = "users"
    __table_args__ = {"comment": "用户表"}

    email: Mapped[str] = mapped_column(
        CaseInsensitiveEmail(), nullable=False, unique=True, index=True, comment="用户邮箱"
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希")
    display_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="用户显示名称"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", comment="是否启用"
    )

    role_links: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.user_id",
    )


class Role(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """
    表示一组后台访问权限的系统角色。

    输入：name、display_name、description 和 is_system。

    输出：Role ORM 实体，可关联用户与权限。
    """

    __tablename__ = "roles"
    __table_args__ = {"comment": "角色表"}

    name: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, comment="角色唯一名称"
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="角色显示名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="角色说明")
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", comment="是否系统内置角色"
    )

    user_links: Mapped[list[UserRole]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    permission_links: Mapped[list[RolePermission]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class Permission(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """
    表示可分配给角色的原子权限。

    输入：code、display_name、description。

    输出：Permission ORM 实体，可通过 role_permissions 关联角色。
    """

    __tablename__ = "permissions"
    __table_args__ = {"comment": "权限表"}

    code: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True, comment="权限唯一编码"
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="权限显示名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="权限说明")

    role_links: Mapped[list[RolePermission]] = relationship(
        back_populates="permission", cascade="all, delete-orphan"
    )


class UserRole(Base):
    """
    表示用户与角色的多对多关联。

    输入：user_id、role_id 与可选 assigned_by。

    输出：UserRole ORM 关联实体。
    """

    __tablename__ = "user_roles"
    __table_args__ = {"comment": "用户角色关联表"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="用户ID",
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        comment="角色ID",
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="分配操作用户ID",
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="角色分配时间",
    )

    user: Mapped[User] = relationship(back_populates="role_links", foreign_keys=[user_id])
    role: Mapped[Role] = relationship(back_populates="user_links")


class RolePermission(Base):
    """
    表示角色与权限的多对多关联。

    输入：role_id、permission_id。

    输出：RolePermission ORM 关联实体。
    """

    __tablename__ = "role_permissions"
    __table_args__ = {"comment": "角色权限关联表"}

    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        comment="角色ID",
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
        comment="权限ID",
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="权限授予时间",
    )

    role: Mapped[Role] = relationship(back_populates="permission_links")
    permission: Mapped[Permission] = relationship(back_populates="role_links")
