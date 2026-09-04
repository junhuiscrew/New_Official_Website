"""GEO 可见性与事实一致性校验。"""

from __future__ import annotations

import re

from app.core.exceptions.handlers import AppException


def _normalize_claim(value: str) -> str:
    """
    归一化用于可见性比较的自然语言文本。

    输入：value，原始文本。
    输出：str，大小写与空白归一化后的文本。
    """
    return re.sub(r"\s+", " ", value).strip().casefold()


def validate_geo_visibility(
    *,
    direct_answer: str | None,
    key_facts: list[str],
    evidence: list[str],
    visible_text: str,
) -> None:
    """
    验证 GEO 答案、事实和证据逐项存在于非 GEO 的用户可见内容中。

    输入：direct_answer、key_facts、evidence 与聚合后的 visible_text。
    输出：None；任一声明缺少可见依据时抛出 AppException。
    """
    normalized_visible = _normalize_claim(visible_text)
    claims = [direct_answer or "", *key_facts, *evidence]
    hidden = [claim for claim in claims if claim.strip() and _normalize_claim(claim) not in normalized_visible]
    if hidden:
        raise AppException(
            409,
            "geo_claim_not_visible",
            "GEO 答案、关键事实和证据必须能在用户可见内容中找到",
            details={"hidden_claims": hidden},
        )
