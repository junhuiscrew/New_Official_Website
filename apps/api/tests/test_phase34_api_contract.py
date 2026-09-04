"""Phase 3.4 Admin、Discovery、Public 与抓取端点契约测试。"""

from app.main import create_app


def test_phase34_routes_are_registered() -> None:
    """
    验证 Phase 3.4 管理、公开内容和搜索交付路由已注册。

    输入：应用工厂。
    输出：None；缺少约定端点时失败。
    """
    app = create_app()
    routes = {(route.path, method) for route in app.routes for method in getattr(route, "methods", set())}
    expected = {
        ("/api/v1/authority/{entity_type}", "GET"),
        ("/api/v1/authority/{entity_type}", "POST"),
        ("/api/v1/authority/{entity_type}/{entity_id}", "PATCH"),
        ("/api/v1/authority/{entity_type}/{entity_id}/relations", "PUT"),
        ("/api/v1/discovery/seo/{owner_type}/{owner_id}/{locale_id}", "PUT"),
        ("/api/v1/discovery/geo/{owner_type}/{owner_id}/{locale_id}", "PUT"),
        ("/api/v1/discovery/geo-visible-source/{owner_type}/{owner_id}/{locale_id}", "GET"),
        ("/api/v1/discovery/sources", "POST"),
        ("/api/v1/discovery/redirects", "POST"),
        ("/api/v1/discovery/health/{owner_type}/{owner_id}/{locale_id}", "GET"),
        ("/api/v1/discovery/url-change", "POST"),
        ("/api/v1/public/redirects/resolve", "GET"),
        ("/api/v1/public/products/{locale_slug}/{category_slug}/{slug}", "GET"),
        ("/api/v1/public/case-studies/{locale_slug}/{slug}", "GET"),
        ("/api/v1/public/knowledge/{locale_slug}/{category_slug}/{slug}", "GET"),
        ("/api/v1/public/experts/{locale_slug}/{slug}", "GET"),
        ("/api/v1/public/product-categories/{locale_slug}/{slug}", "GET"),
        ("/api/v1/public/{resource}/{locale_slug}/{slug}", "GET"),
        ("/sitemap.xml", "GET"),
        ("/robots.txt", "GET"),
        ("/llms.txt", "GET"),
    }
    assert expected.issubset(routes)


def test_nginx_routes_root_discovery_files_to_api() -> None:
    """Nginx 外部入口必须把 Sitemap、Robots 与 llms.txt 转发给统一 API。"""
    from pathlib import Path

    # Docker 测试镜像把契约文件放在 /workspace，本机则从仓库层级解析。
    workspace_root = Path("/workspace")
    repository_root = (
        workspace_root if workspace_root.exists() else Path(__file__).resolve().parents[3]
    )
    for filename in ("nginx.conf", "nginx.staging.conf"):
        source = (repository_root / "infra" / "nginx" / filename).read_text(encoding="utf-8")
        assert "sitemap\\.xml|robots\\.txt|llms\\.txt" in source
        assert "http://api:8000" in source
