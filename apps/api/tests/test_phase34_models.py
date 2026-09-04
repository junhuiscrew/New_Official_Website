"""Phase 3.4 Authority Content 与 SEO/GEO 数据模型契约测试。"""

from app.core.database import Base


def test_authority_content_tables_are_registered() -> None:
    """
    验证 Authority Content 主表、翻译表和显式关系表已注册。

    输入：无。
    输出：None；缺表时由 pytest 报告。
    """
    from app.modules.authority import models as _authority_models  # noqa: F401

    expected = {
        "case_studies",
        "case_study_translations",
        "case_products",
        "case_materials",
        "case_technologies",
        "case_applications",
        "case_solutions",
        "knowledge_categories",
        "knowledge_category_translations",
        "knowledge_articles",
        "knowledge_article_translations",
        "article_products",
        "article_materials",
        "article_technologies",
        "article_applications",
        "article_solutions",
        "article_cases",
        "article_faqs",
        "faqs",
        "faq_translations",
        "faq_products",
        "faq_materials",
        "faq_solutions",
        "faq_articles",
        "faq_cases",
        "author_experts",
        "author_expert_translations",
    }
    assert expected.issubset(Base.metadata.tables)


def test_authority_columns_have_chinese_comments() -> None:
    """
    验证新增数据库字段均带中文注释。

    输入：无。
    输出：None；任一字段缺少注释时失败。
    """
    from app.modules.authority import models as _authority_models  # noqa: F401

    authority_tables = {
        name: table
        for name, table in Base.metadata.tables.items()
        if name.startswith(("case_", "knowledge_", "article_", "faq_", "author_expert"))
    }
    assert authority_tables
    for table in authority_tables.values():
        for column in table.columns:
            assert column.comment, f"{table.name}.{column.name} 缺少中文字段注释"


def test_faq_has_no_independent_publication_or_route_foreign_key() -> None:
    """
    验证 FAQ 仅作为页面可见模块，不建立第二套或独立发布路由字段。

    输入：无。
    输出：None；发现 publication/route 字段时失败。
    """
    from app.modules.authority import models as _authority_models  # noqa: F401

    faq_columns = set(Base.metadata.tables["faqs"].columns.keys())
    assert "publication_id" not in faq_columns
    assert "route_id" not in faq_columns


def test_discovery_delivery_tables_are_registered() -> None:
    """
    验证统一 SEO/GEO、来源引用和 Redirect 数据表已注册。

    输入：无。
    输出：None；缺表时由 pytest 报告。
    """
    from app.modules.discovery import models as _discovery_models  # noqa: F401

    assert {
        "seo_documents",
        "geo_documents",
        "source_citations",
        "redirect_rules",
    }.issubset(Base.metadata.tables)


def test_discovery_owner_locale_uniqueness() -> None:
    """
    验证 SEO/GEO 使用统一 owner + locale 唯一约束。

    输入：无。
    输出：None；唯一约束缺失时失败。
    """
    from app.modules.discovery import models as _discovery_models  # noqa: F401

    for table_name in ("seo_documents", "geo_documents"):
        table = Base.metadata.tables[table_name]
        unique_columns = {
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        assert ("owner_type", "owner_id", "locale_id") in unique_columns
