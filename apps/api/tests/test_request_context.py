"""可信代理审计上下文解析测试。"""

from starlette.requests import Request

from app.core.config import get_settings
from app.core.request_context import get_client_context


def _request(peer_ip: str, forwarded_for: str) -> Request:
    """构造带 peer 与转发头的最小 Starlette Request。"""
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [
                (b"x-forwarded-for", forwarded_for.encode()),
                (b"user-agent", b"phase32-test-agent"),
            ],
            "client": (peer_ip, 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_trusted_proxy_can_supply_single_valid_client_ip(monkeypatch) -> None:
    """验证受信网段中的唯一边缘代理可提供最终客户端 IP。"""
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", '["172.16.0.0/12"]')
    get_settings.cache_clear()
    assert get_client_context(_request("172.20.0.5", "203.0.113.24")) == (
        "203.0.113.24",
        "phase32-test-agent",
    )


def test_untrusted_or_chained_forwarded_header_is_ignored(monkeypatch) -> None:
    """验证非受信 peer 与可伪造的多段转发链不会覆盖直连地址。"""
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", '["172.16.0.0/12"]')
    get_settings.cache_clear()
    assert get_client_context(_request("198.51.100.10", "203.0.113.24"))[0] == "198.51.100.10"
    assert get_client_context(_request("172.20.0.5", "1.2.3.4, 203.0.113.24"))[0] == "172.20.0.5"
