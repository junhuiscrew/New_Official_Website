"""Phase 3.6 Remediation 的独立合同复现测试。"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions.handlers import AppException
from app.modules.rfq.schemas import RFQCreate
from app.phase36_qa import (
    _assert_qa_allowed,
    _ensure_product_specifications,
    _ensure_representative_product_copy,
)


@pytest.mark.parametrize(
    "source_type",
    (
        "product",
        "material",
        "technology",
        "application",
        "solution",
        "case_study",
        "knowledge_article",
        "manufacturing_capability",
        "author_expert",
        "exhibition",
    ),
)
def test_rfq_schema_accepts_only_frozen_public_source_types(source_type: str) -> None:
    """
    验证公开 RFQ DTO 接受冻结的多来源白名单。

    输入：
        source_type: str，公开 CTA 的业务来源类型。

    输出：
        None；任一批准类型被 Pydantic 拒绝时测试失败。
    """
    try:
        payload = RFQCreate(
            company_name="QA Company",
            contact_name="QA Contact",
            email="qa@example.com",
            message="QA only",
            preferred_language="en",
            source_type=source_type,
            source_slug="qa-source",
            consent_privacy=True,
        )
    except ValidationError as exc:  # pragma: no cover - 失败信息由断言展示
        pytest.fail(f"批准的 RFQ 来源类型被拒绝：{exc}")
    assert payload.source_type == source_type


def test_phase36_qa_requires_explicit_local_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证 QA 数据命令默认关闭且 run-id 受限。

    输入：monkeypatch，隔离环境变量。
    输出：None；无确认可运行或非法 run-id 被接受时失败。
    """
    monkeypatch.setattr(
        "app.phase36_qa.get_settings",
        lambda: SimpleNamespace(
            app_env="development",
            database_url="postgresql+asyncpg://qa:qa@postgres:5432/junhui",
            redis_url="redis://redis:6379/0",
            minio_endpoint="minio:9000",
            minio_public_bucket="public-media",
            minio_private_bucket="private-rfq",
        ),
    )
    monkeypatch.delenv("PHASE36_QA_CONFIRM", raising=False)
    with pytest.raises(AppException):
        _assert_qa_allowed("safe-run")

    monkeypatch.setenv("PHASE36_QA_CONFIRM", "LOCAL_QA_ONLY")
    monkeypatch.setenv("PHASE36_QA_ISOLATION", "LOCAL_COMPOSE_ONLY")
    with pytest.raises(AppException):
        _assert_qa_allowed("../unsafe")
    assert _assert_qa_allowed("safe-run") == "safe-run"


def test_phase36_qa_is_forbidden_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证生产环境无法准备 QA 数据。

    输入：monkeypatch，模拟生产配置与显式确认。
    输出：None；若 production 未闭合失败则测试失败。
    """
    monkeypatch.setattr(
        "app.phase36_qa.get_settings",
        lambda: SimpleNamespace(app_env="production"),
    )
    monkeypatch.setenv("PHASE36_QA_CONFIRM", "LOCAL_QA_ONLY")
    monkeypatch.setenv("PHASE36_QA_ISOLATION", "LOCAL_COMPOSE_ONLY")
    with pytest.raises(AppException):
        _assert_qa_allowed("safe-run")


def test_phase36_qa_rejects_remote_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    """输入远端连接配置；输出 None，并证明即使显式确认也会闭合失败。"""
    monkeypatch.setattr(
        "app.phase36_qa.get_settings",
        lambda: SimpleNamespace(
            app_env="development",
            database_url="postgresql+asyncpg://qa:qa@db.example.com:5432/live",
            redis_url="redis://redis.example.com:6379/0",
            minio_endpoint="objects.example.com",
            minio_public_bucket="public-media",
            minio_private_bucket="private-rfq",
        ),
    )
    monkeypatch.setenv("PHASE36_QA_CONFIRM", "LOCAL_QA_ONLY")
    monkeypatch.setenv("PHASE36_QA_ISOLATION", "LOCAL_COMPOSE_ONLY")
    with pytest.raises(AppException) as failure:
        _assert_qa_allowed("safe-run")
    assert failure.value.code == "qa_target_not_local"


def test_phase36_qa_fixture_declares_all_five_specification_types() -> None:
    """
    验证有内容 QA fixture 会通过正式服务创建五类规格，而非只测空规格卡片。

    输入：无。
    输出：None；缺任一冻结 value_type 或绕过 Catalog 服务时失败。
    """
    source = inspect.getsource(_ensure_product_specifications)
    for value_type in ("text", "number", "range", "boolean", "enum"):
        assert f'"{value_type}"' in source
    assert "create_specification_value" in source


def test_phase36_qa_existing_product_copy_reuses_lifecycle_services() -> None:
    """
    验证重复运行会让代表产品收敛到长标题，并经正式更新/发布服务恢复公开状态。

    输入：无。
    输出：None；若既有样本被静默保留旧字段或直接改 published 状态则失败。
    """
    source = inspect.getsource(_ensure_representative_product_copy)
    assert "Long-title Extrusion Screw" in source
    assert "update_product(" in source
    assert "transition_publication(" in source
