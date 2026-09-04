"""健康检查接口测试。"""

from fastapi.testclient import TestClient

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
            "version": "0.1.0",
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
