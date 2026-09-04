"""在显式信任边界内解析客户端审计上下文。"""

from ipaddress import ip_address, ip_network

from fastapi import Request

from app.core.config import get_settings


def get_client_context(request: Request) -> tuple[str | None, str | None]:
    """
    从直连 peer 或受信反向代理头解析审计 IP 与 User-Agent。

    输入：
        request: Request，当前 FastAPI 请求。

    输出：tuple[str | None, str | None]，可信客户端 IP 与 User-Agent。
    """
    peer_ip = request.client.host if request.client else None
    client_ip = peer_ip
    if peer_ip:
        try:
            peer_address = ip_address(peer_ip)
            trusted = any(
                peer_address in ip_network(cidr, strict=False)
                for cidr in get_settings().trusted_proxy_cidrs
            )
        except ValueError:
            trusted = False
        forwarded_for = request.headers.get("x-forwarded-for", "").strip()
        # 唯一边缘 Nginx 覆盖该头；包含逗号的链不在本阶段信任范围内。
        if trusted and forwarded_for and "," not in forwarded_for:
            try:
                client_ip = str(ip_address(forwarded_for))
            except ValueError:
                client_ip = peer_ip
    return client_ip, request.headers.get("user-agent")
