"""Catalog 写事务响应对象的回归测试。"""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.api.v1.catalog import _write_result
from app.modules.catalog.models import Product


@pytest.mark.asyncio
async def test_write_result_refreshes_mapped_entity_after_commit() -> None:
    """
    验证提交后刷新 ORM 实体，避免真实 PostgreSQL 响应序列化触发异步懒加载。

    输入：模拟异步 session 与一个 Product ORM 实体。

    输出：提交和刷新均执行一次，并返回原实体。
    """
    session = AsyncMock()
    product = Product(
        id=uuid.uuid4(),
        category_id=uuid.uuid4(),
        code="DEMO-RESPONSE",
        slug="demo-response",
        status="enabled",
        featured=False,
        sort_order=0,
    )

    async def operation() -> Product:
        """返回待提交的映射实体。"""
        return product

    result = await _write_result(session, operation())

    assert result is product
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(product)


@pytest.mark.asyncio
async def test_write_result_does_not_refresh_scalar_result() -> None:
    """
    验证删除类写操作返回 UUID 时不会错误调用 ORM refresh。

    输入：模拟异步 session 与 UUID 标量结果。

    输出：提交执行一次，refresh 不执行，并返回原 UUID。
    """
    session = AsyncMock()
    deleted_id = uuid.uuid4()

    async def operation() -> uuid.UUID:
        """返回待提交的 UUID 标量。"""
        return deleted_id

    result = await _write_result(session, operation())

    assert result == deleted_id
    session.commit.assert_awaited_once_with()
    session.refresh.assert_not_awaited()
