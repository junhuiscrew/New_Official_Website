"""健康检查接口测试。"""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import health as health_module
from app.core.database import create_database_engine, create_session_factory, get_session
from app.main import create_app


def test_health_endpoint_returns_standard_response() -> None:
    """
    验证健康检查使用统一响应结构并报告服务状态。

    输入：无。

    输出：None；断言失败时由 pytest 报告。
    """
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "Junhui Global Website API",
                "version": "0.4.0",
        },
        "error": None,
    }


def test_unknown_api_route_uses_standard_error_response() -> None:
    """
    验证框架级 404 也转换为统一错误结构。

    输入：无。

    输出：None；断言失败时由 pytest 报告。
    """
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/not-found")

    assert response.status_code == 404
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "not_found"


def test_liveness_does_not_require_external_dependencies() -> None:
    """验证 live 端点只报告进程状态。"""
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "healthy"


async def test_readiness_checks_postgresql_and_redis(
    sqlite_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    验证 ready 端点同时执行数据库和 Redis 探针。

    输入：sqlite_database_url 与 monkeypatch。

    输出：None；断言两个依赖均报告 ready。
    """
    engine = create_database_engine(sqlite_database_url)
    factory = create_session_factory(engine)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    async def redis_ready(_redis_url: str) -> bool:
        return True

    monkeypatch.setattr(health_module, "_check_redis", redis_ready)
    app = create_app()
    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/health/ready")
    await engine.dispose()

    assert response.status_code == 200
    assert response.json()["data"]["dependencies"] == {
        "postgresql": "ready",
        "redis": "ready",
    }


async def test_readiness_returns_503_when_redis_is_unavailable(
    sqlite_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证关键依赖不可用时 ready 返回 503。"""
    engine = create_database_engine(sqlite_database_url)
    factory = create_session_factory(engine)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    async def redis_unavailable(_redis_url: str) -> bool:
        return False

    monkeypatch.setattr(health_module, "_check_redis", redis_unavailable)
    app = create_app()
    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/health/ready")
    await engine.dispose()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_not_ready"
