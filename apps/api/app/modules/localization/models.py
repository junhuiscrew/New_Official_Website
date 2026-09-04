"""站点语言配置模型。"""

from __future__ import annotations

from sqlalchemy import Boolean, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin


class Locale(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """
    表示一个可发布的站点语言及其 URL 片段。

    输入：标准语言代码、URL slug、名称、启用状态和排序。

    输出：Locale ORM 实体，供未来翻译表统一引用。
    """

    __tablename__ = "locales"
    __table_args__ = (
        Index(
            "ux_locales_single_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default = 1"),
        ),
        {"comment": "站点语言表"},
    )

    code: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True, index=True, comment="标准语言代码"
    )
    slug: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True, index=True, comment="语言URL路径标识"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="语言英文名称")
    native_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="语言本地名称")
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", comment="是否默认语言"
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="是否启用：true启用，false停用",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="显示排序值"
    )
