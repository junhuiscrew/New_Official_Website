"""API CORS allowlist 行为测试。"""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_configured_origin_receives_credential_cors_headers(monkeypatch) -> None:
    """
    验证显式允许的 Admin Origin 可以携带 Cookie 调用 API。

    输入：
        monkeypatch: pytest.MonkeyPatch，用于覆盖 Origin 配置。

    输出：None；断言预检响应的 Origin 与 credentials header。
    """
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3001"]')
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        response = client.options(
            "/api/v1/health/live",
            headers={
                "Origin": "http://localhost:3001",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_unconfigured_origin_is_not_reflected(monkeypatch) -> None:
    """
    验证未配置的 Origin 不会获得跨域授权。

    输入：
        monkeypatch: pytest.MonkeyPatch，用于覆盖 Origin 配置。

    输出：None；断言响应不反射恶意 Origin。
    """
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3001"]')
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        response = client.options(
            "/api/v1/health/live",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.headers.get("access-control-allow-origin") is None
