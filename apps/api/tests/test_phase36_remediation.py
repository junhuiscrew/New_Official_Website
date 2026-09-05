"""Phase 3.6 Remediation 的独立合同复现测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions.handlers import AppException
from app.modules.rfq.schemas import RFQCreate
from app.phase36_qa import _assert_qa_allowed


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
        lambda: SimpleNamespace(app_env="development"),
    )
    monkeypatch.delenv("PHASE36_QA_CONFIRM", raising=False)
    with pytest.raises(AppException):
        _assert_qa_allowed("safe-run")

    monkeypatch.setenv("PHASE36_QA_CONFIRM", "LOCAL_QA_ONLY")
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
    with pytest.raises(AppException):
        _assert_qa_allowed("safe-run")
