"""Admin/Staging 索引安全与 migration runtime 文档契约测试。"""

import os
from pathlib import Path

_configured_project_root = os.getenv("PROJECT_ROOT")
PROJECT_ROOT = (
    Path(_configured_project_root)
    if _configured_project_root
    else Path(__file__).resolve().parents[3]
)


def test_admin_applies_global_meta_and_x_robots_tag() -> None:
    """验证 Admin 不依赖单页手写 noindex。"""
    config = (PROJECT_ROOT / "apps/admin/nuxt.config.ts").read_text(encoding="utf-8")
    assert "noindex, nofollow" in config
    assert "X-Robots-Tag" in config


def test_staging_nginx_requires_basic_auth_and_blocks_indexing() -> None:
    """验证 staging 入口同时启用 Basic Auth 和全站 X-Robots-Tag。"""
    nginx = (PROJECT_ROOT / "infra/nginx/nginx.staging.conf").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "docker-compose.staging.yml").read_text(encoding="utf-8")
    assert "auth_basic" in nginx
    assert "auth_basic_user_file /etc/nginx/staging.htpasswd" in nginx
    assert 'add_header X-Robots-Tag "noindex, nofollow" always' in nginx
    assert "STAGING_HTPASSWD_FILE" in compose
    assert compose.count("ports: !reset []") == 6
    assert "MINIO_ROOT_PASSWORD" in compose
    assert "MINIO_ROOT_USER" in compose
    assert "TRUSTED_PROXY_CIDRS" in compose
    assert "proxy_pass $admin_upstream;" in nginx
    assert "proxy_set_header X-Forwarded-For $remote_addr" in nginx


def test_frontend_images_run_production_servers() -> None:
    """验证 Website/Admin 镜像运行构建产物而非开发服务器。"""
    for app_name in ("website", "admin"):
        dockerfile = (PROJECT_ROOT / f"apps/{app_name}/Dockerfile").read_text(encoding="utf-8")
        assert "pnpm build" in dockerfile
        assert 'CMD ["node", ".output/server/index.mjs"]' in dockerfile
        assert 'CMD ["pnpm", "dev"' not in dockerfile


def test_runtime_strategy_orders_migration_seed_before_api() -> None:
    """验证正式运行策略明确 migration job、Seed、API 的严格顺序。"""
    strategy = (PROJECT_ROOT / "docs/architecture/migration-runtime-strategy.md").read_text(
        encoding="utf-8"
    )
    migration_position = strategy.index("alembic upgrade head")
    seed_position = strategy.index("python -m app.cli seed")
    api_position = strategy.index("uvicorn app.main:app")
    assert migration_position < seed_position < api_position


def test_docker_api_healthcheck_uses_ready_endpoint() -> None:
    """验证 Docker 编排以依赖就绪探针判定 API healthy。"""
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "http://localhost:8000/api/v1/health/ready" in compose
