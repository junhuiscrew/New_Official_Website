"""Alembic 运行环境：连接应用配置与 SQLAlchemy metadata。"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.core.database import Base
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.authority import models as authority_models  # noqa: F401
from app.modules.catalog import models as catalog_models  # noqa: F401
from app.modules.company import models as company_models  # noqa: F401
from app.modules.content import models as content_models  # noqa: F401
from app.modules.demo import models as demo_models  # noqa: F401
from app.modules.discovery import models as discovery_models  # noqa: F401
from app.modules.localization import models as localization_models  # noqa: F401
from app.modules.media import models as media_models  # noqa: F401
from app.modules.presentation import models as presentation_models  # noqa: F401
from app.modules.privacy import models as privacy_models  # noqa: F401
from app.modules.rfq import models as rfq_models  # noqa: F401
from app.modules.users import models as user_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    在不创建 Engine 的情况下生成离线迁移 SQL。

    输入：从 Alembic 全局 context 读取配置。

    输出：None；迁移 SQL 被写入 Alembic 输出流。
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    在已建立的同步连接桥接层中执行迁移。

    输入：
        connection: Connection，由 AsyncEngine 提供的同步代理连接。

    输出：None；数据库 schema 被升级或降级。
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    创建异步引擎并执行在线迁移。

    输入：从 Alembic 配置读取数据库 URL。

    输出：None；完成后释放数据库引擎。
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """
    从同步 Alembic 入口启动异步在线迁移。

    输入：无。

    输出：None；在线 migration 执行完成。
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
