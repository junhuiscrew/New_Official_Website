"""在显式信任边界内解析客户端审计上下文。"""

from ipaddress import ip_address, ip_network

from fastapi import Request

from app.core.config import get_settings


def get_client_ip(request: Request) -> str | None:
    """
    在受信代理边界内解析真实客户端 IP。

    输入：
        request: Request，当前 FastAPI 请求。

    输出：str | None，直连客户端或受信代理链最左侧的合法客户端 IP。
    """
    # 代理必须位于 trusted_proxy_cidrs；否则忽略所有转发头，避免伪造来源。
    peer_ip = request.client.host if request.client else None
    if not peer_ip:
        return None
    networks = [ip_network(cidr, strict=False) for cidr in get_settings().trusted_proxy_cidrs]

    def _is_trusted(value: str) -> bool:
        """输入 IP 字符串；输出其是否位于明确配置的代理网段。"""
        try:
            return any(ip_address(value) in network for network in networks)
        except ValueError:
            return False

    if not _is_trusted(peer_ip):
        return peer_ip

    forwarded_chain = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
    if not forwarded_chain:
        return peer_ip
    try:
        normalized_chain = [str(ip_address(candidate)) for candidate in forwarded_chain]
    except ValueError:
        return peer_ip
    # 从直连 peer 向左剥离受信代理，停在第一个不受信地址，避免盲信可伪造的最左值。
    current = peer_ip
    for candidate in reversed(normalized_chain):
        if not _is_trusted(current):
            break
        current = candidate
    return current


def get_client_context(request: Request) -> tuple[str | None, str | None]:
    """
    从可信网络边界解析审计 IP 与 User-Agent。

    输入：
        request: Request，当前 FastAPI 请求。

    输出：tuple[str | None, str | None]，可信客户端 IP 与 User-Agent。
    """
    return get_client_ip(request), request.headers.get("user-agent")
