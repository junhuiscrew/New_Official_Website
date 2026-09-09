"""发现层写接口事务响应顺序回归测试。"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1 import discovery
from app.modules.discovery import services as discovery_services
from app.modules.discovery.models import GeoDocument
from app.modules.discovery.schemas import GeoDocumentUpsert


@pytest.mark.asyncio
async def test_geo_endpoint_serializes_before_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证 GEO 写接口在提交事务前完成同步序列化。

    输入：模拟会话、用户和 GEO 文档。
    输出：None；若 commit 导致 ORM 过期后才读取字段则测试失败。
    """
    events: list[str] = []
    document = object()
    session = AsyncMock()
    user = SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(
        discovery,
        "upsert_geo_document",
        AsyncMock(return_value=document),
    )

    def serialize(value: object) -> dict[str, str]:
        assert value is document
        events.append("serialize")
        return {"id": "demo-geo"}

    async def commit(value: object) -> None:
        assert value is session
        events.append("commit")

    monkeypatch.setattr(discovery, "_serialize", serialize)
    monkeypatch.setattr(discovery, "_commit", commit)

    response = await discovery.put_geo_document(
        owner_type="knowledge_article",
        owner_id=uuid.uuid4(),
        locale_id=uuid.uuid4(),
        payload=GeoDocumentUpsert(direct_answer="Visible demo fact"),
        session=session,
        user=user,
        _csrf=None,
    )

    assert events == ["serialize", "commit"]
    assert response.data == {"id": "demo-geo"}


@pytest.mark.asyncio
async def test_geo_service_refreshes_document_after_flush(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    验证 GEO 服务在 flush 后显式刷新 ORM 文档。

    输入：已有 GEO 文档与模拟异步会话。
    输出：None；若返回可能已过期对象则测试失败。
    """
    owner_id = uuid.uuid4()
    locale_id = uuid.uuid4()
    document = GeoDocument(
        id=uuid.uuid4(),
        owner_type="knowledge_article",
        owner_id=owner_id,
        locale_id=locale_id,
        direct_answer="Visible demo fact",
    )
    session = AsyncMock()
    session.scalar.return_value = document
    monkeypatch.setattr(
        discovery_services,
        "_reject_case_private_identity",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        discovery_services,
        "build_visible_source_text",
        AsyncMock(return_value="Visible demo fact"),
    )
    monkeypatch.setattr(discovery_services, "write_audit_log", lambda *args, **kwargs: None)

    result = await discovery_services.upsert_geo_document(
        session,
        "knowledge_article",
        owner_id,
        locale_id,
        GeoDocumentUpsert(direct_answer="Visible demo fact"),
        uuid.uuid4(),
    )

    assert result is document
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(document)
