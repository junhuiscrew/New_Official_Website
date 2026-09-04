"""使用 Pydantic Settings 管理环境变量与运行配置。"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    定义 API、数据库、缓存和对象存储的类型化配置。

    输入：由 Pydantic Settings 从环境变量或 `.env` 文件读取。

    输出：Settings，经过类型校验的不可变配置对象。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    app_env: str = "development"
    app_name: str = "Junhui Global Website API"
    app_version: str = "0.1.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+asyncpg://junhui:junhui-local-dev@localhost:5432/junhui"
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "junhui-local-admin"
    minio_secret_key: str = Field(default="change-me-minio-local-only", repr=False)
    minio_secure: bool = False
    minio_public_bucket: str = "public-media"
    minio_private_bucket: str = "private-rfq"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    获取进程内缓存的应用配置。

    输入：无。

    输出：Settings，当前进程使用的配置对象。
    """
    return Settings()
