"""MinIO/S3 对象存储适配器，统一公共媒体与 RFQ 私有文件的真实读写。"""

from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from minio import Minio

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException


class MinioStorageAdapter:
    """
    封装 MinIO 官方 SDK，并将阻塞调用移出异步事件循环。

    输入：
        client: Any | None，内部读写客户端；测试可注入兼容对象。
        public_client: Any | None，生成浏览器可访问预签名 URL 的客户端。

    输出：MinioStorageAdapter，可用于对象写入、读取、删除、检查与签名。
    """

    def __init__(self, client: Any | None = None, public_client: Any | None = None) -> None:
        settings = get_settings()
        self.client = client or Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_internal_secure,
            region=settings.minio_region,
        )
        self.public_client = public_client or Minio(
            settings.minio_public_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_public_secure,
            # 显式 region 可避免签名阶段访问浏览器公网端点探测 bucket。
            region=settings.minio_region,
        )

    async def put_object(self, bucket: str, key: str, content: bytes, content_type: str) -> None:
        """输入桶、对象键、字节和 MIME；输出 None，成功时对象已经写入。"""
        await asyncio.to_thread(
            self.client.put_object,
            bucket,
            key,
            io.BytesIO(content),
            len(content),
            content_type=content_type,
        )

    async def get_object(self, bucket: str, key: str) -> bytes:
        """输入桶和对象键；输出对象完整字节，并可靠释放 HTTP 连接。"""

        def _read() -> bytes:
            response = self.client.get_object(bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(_read)

    async def delete_object(self, bucket: str, key: str) -> None:
        """输入桶和对象键；输出 None，用于回滚或生命周期删除。"""
        await asyncio.to_thread(self.client.remove_object, bucket, key)

    async def object_exists(self, bucket: str, key: str) -> bool:
        """输入桶和对象键；输出 bool，任何明确不存在结果均返回 False。"""
        try:
            await asyncio.to_thread(self.client.stat_object, bucket, key)
            return True
        except Exception:
            return False

    async def presigned_get(
        self, bucket: str, key: str, *, ttl_seconds: int = 600
    ) -> str:
        """
        输入桶、对象键和有效期；输出官方 S3 Presigned GET URL。

        官方 SDK 依据外部端点签名；有效期由调用方同步返回。
        """
        if not key or key.startswith("/") or ".." in key:
            raise AppException(409, "unsafe_storage_key", "私有文件路径不安全")
        ttl = min(max(ttl_seconds, 60), 900)
        url = await asyncio.to_thread(
            self.public_client.presigned_get_object,
            bucket,
            key,
            expires=timedelta(seconds=ttl),
        )
        # 生产环境绝不允许把私有文件凭据放进明文 HTTP URL。
        if get_settings().app_env == "production" and urlparse(url).scheme != "https":
            raise AppException(503, "insecure_presigned_url", "生产环境私有下载地址必须使用 HTTPS")
        return url


def get_storage_adapter() -> MinioStorageAdapter:
    """输入无；输出当前运行环境的 MinIO 对象存储适配器。"""
    return MinioStorageAdapter()


def private_url_expiry(ttl_seconds: int = 600) -> datetime:
    """输入签名有效秒数；输出经过 60~900 秒边界约束的 UTC 过期时间。"""
    return datetime.now(UTC) + timedelta(seconds=min(max(ttl_seconds, 60), 900))
