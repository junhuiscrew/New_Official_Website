"""恶意文件扫描接口与安全状态机。"""

from __future__ import annotations

import asyncio
import socket
import struct
import uuid
from typing import Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.media.models import MediaAsset

ScanResult = Literal["clean", "infected", "failed"]


class MalwareScanner(Protocol):
    """恶意文件扫描器协议，便于 ClamAV 与测试替身统一接入。"""

    async def scan_bytes(self, content: bytes) -> ScanResult:
        """输入文件字节；输出 clean、infected 或 failed。"""
        ...


class ClamAVScanner:
    """通过 ClamAV INSTREAM 协议扫描内存文件，不写入本地公共目录。"""

    async def scan_bytes(self, content: bytes) -> ScanResult:
        """输入文件字节；输出 ClamAV 扫描结论，连接异常按 failed 处理。"""
        settings = get_settings()

        def _scan() -> ScanResult:
            try:
                with socket.create_connection(
                    (settings.malware_scanner_host, settings.malware_scanner_port),
                    timeout=settings.malware_scanner_timeout_seconds,
                ) as connection:
                    connection.sendall(b"zINSTREAM\0")
                    for offset in range(0, len(content), 1024 * 1024):
                        chunk = content[offset : offset + 1024 * 1024]
                        connection.sendall(struct.pack(">I", len(chunk)) + chunk)
                    connection.sendall(struct.pack(">I", 0))
                    response = connection.recv(4096).decode("utf-8", errors="replace")
                if " FOUND" in response:
                    return "infected"
                return "clean" if response.rstrip("\0\n").endswith(" OK") else "failed"
            except OSError:
                return "failed"

        return await asyncio.to_thread(_scan)


async def apply_scan_result(
    session: AsyncSession, asset_id: uuid.UUID, result: ScanResult
) -> MediaAsset:
    """
    应用扫描结果并执行 fail-closed 状态转换。

    输入：session 数据库会话、asset_id 媒体 ID、result 扫描结论。
    输出：MediaAsset，已经更新的媒体资产。
    """
    asset = await session.get(MediaAsset, asset_id)
    if asset is None:
        raise AppException(404, "media_not_found", "待扫描媒体不存在")
    asset.malware_scan_status = result
    asset.upload_status = "ready" if result == "clean" else "quarantined"
    return asset
