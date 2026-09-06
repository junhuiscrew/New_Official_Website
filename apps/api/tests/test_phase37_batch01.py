"""Phase 3.7 Batch01 导入器的范围和空参数门禁测试。"""

from __future__ import annotations

from types import SimpleNamespace

from app.phase37_batch01 import BatchState, _build_plan, _mapped_action


def test_mapped_action_requires_private_mapping_for_existing_resource() -> None:
    """
    验证自然键相同但没有私有映射时不能静默接管已有内容。

    输入：无。
    输出：None；保守冲突或幂等 no-op 失效时测试失败。
    """
    items = [{"id": "existing-id", "slug": "nitrided-screw"}]

    assert (
        _mapped_action(
            items,
            field="slug",
            value="nitrided-screw",
            mapped_id=None,
        )
        == "conflict"
    )
    assert (
        _mapped_action(
            items,
            field="slug",
            value="nitrided-screw",
            mapped_id="existing-id",
        )
        == "no-op"
    )


def test_batch_plan_preserves_existing_pilot_and_keeps_values_empty() -> None:
    """
    验证既有 nitrided-barrel 不被覆盖，且参数值状态始终明确为空。

    输入：无。
    输出：None；安全 slug 方案、IMG-05 门禁或空值策略回归时测试失败。
    """
    package = {
        "definitions": [
            {"external_key": f"F{index:02d}", "proposed_code": f"field-{index}"}
            for index in range(1, 8)
        ]
    }
    remote = {
        "categories": [],
        "products": [{"id": "pilot-id", "slug": "nitrided-barrel"}],
        "groups": [],
        "definitions": [],
        "media": [],
        "company": {"profile": None},
    }
    derivatives = {
        source_id: SimpleNamespace(sha256="a" * 64, width=700, height=700, size_bytes=100)
        for source_id in ("IMG-01", "IMG-02", "IMG-03", "IMG-04")
    }

    plan = _build_plan(package, BatchState(), remote, derivatives)

    assert plan["status"] == "ready"
    assert plan["products"] == {"P01": "create", "P02": "create", "P03": "create"}
    assert plan["proposed_slug_conflict"]["P02"] == {
        "proposed": "nitrided-barrel",
        "existing": True,
        "effective_draft_slug": "junhui-nitrided-barrel",
        "resolution": "preserve_existing_and_create_distinct_draft",
    }
    assert plan["product_spec_values"] == "VALUES_INTENTIONALLY_EMPTY"
    assert plan["internal_reference_img05"] == "blocked_publication"
