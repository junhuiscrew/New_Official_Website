"""使用 Pydantic Settings 管理环境变量与运行配置。"""

from __future__ import annotations

from functools import lru_cache
from ipaddress import ip_address, ip_network
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


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

    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "Junhui Global Website API"
    app_version: str = "0.4.0"
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

    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8080",
    ]
    jwt_signing_secret: str = Field(default="change-me-jwt-local-only", repr=False)
    refresh_token_secret: str = Field(default="change-me-refresh-local-only", repr=False)
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    public_sitemap_enabled: bool = True
    llms_txt_enabled: bool = True
    faq_schema_enabled: bool = False
    analytics_enabled: bool = False
    marketing_email_enabled: bool = False
    trusted_proxy_cidrs: list[str] = []

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_environment(cls, value: object) -> object:
        """
        归一化环境名并由 Literal 拒绝未知别名，防止安全策略静默降级。

        输入：
            value: object，环境变量或构造参数提供的原始值。

        输出：object，字符串环境名会转为小写并去除首尾空白。
        """
        return value.strip().lower() if isinstance(value, str) else value

    @staticmethod
    def _is_local_origin_hostname(hostname: str) -> bool:
        """
        判断 CORS hostname 是否指向本机或 loopback。

        输入：
            hostname: str，已由 URL parser 提取的主机名。

        输出：bool，localhost 子域、loopback 或未指定 IP 返回 true。
        """
        normalized = hostname.lower().rstrip(".")
        if normalized == "localhost" or normalized.endswith(".localhost"):
            return True
        try:
            address = ip_address(normalized)
            mapped_address = getattr(address, "ipv4_mapped", None)
            mapped_loopback = bool(mapped_address and mapped_address.is_loopback)
            return (
                address.is_loopback
                or address.is_unspecified
                or address.is_link_local
                or mapped_loopback
            )
        except ValueError:
            return False

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def validate_trusted_proxy_cidrs(cls, values: list[str]) -> list[str]:
        """
        验证受信代理网段采用合法 CIDR，避免错误配置静默失效。

        输入：
            values: list[str]，允许提供客户端地址头的代理网段。

        输出：list[str]，原始合法 CIDR 列表。
        """
        for value in values:
            ip_network(value, strict=False)
        return values

    @model_validator(mode="after")
    def validate_runtime_security(self) -> Settings:
        """
        拒绝危险的跨域配置，并让 staging/production 对示例 Secret 失败快。

        输入：
            self: Settings，已完成字段解析的配置对象。

        输出：
            Settings，通过安全约束校验的当前配置。
        """
        if "*" in self.cors_allowed_origins:
            raise ValueError("Cookie authentication forbids wildcard CORS origins")

        if self.app_env == "development":
            return self

        environment = self.app_env
        insecure_markers = ("change-me", "local-dev", "localhost")
        protected_values = {
            "database_url": self.database_url,
            "minio_secret_key": self.minio_secret_key,
            "jwt_signing_secret": self.jwt_signing_secret,
            "refresh_token_secret": self.refresh_token_secret,
        }
        invalid_fields = [
            field_name
            for field_name, value in protected_values.items()
            if len(value) < 24 or any(marker in value.lower() for marker in insecure_markers)
        ]
        if environment in {"staging", "production"}:
            try:
                parsed_database_url = make_url(self.database_url)
                if not parsed_database_url.username or not parsed_database_url.password:
                    invalid_fields.append("database_url")
            except Exception:
                invalid_fields.append("database_url")
        if not self.cors_allowed_origins:
            invalid_fields.append("cors_allowed_origins")
        if environment in {"staging", "production"}:
            parsed_origins = [urlparse(origin) for origin in self.cors_allowed_origins]
            if any(
                origin.scheme != "https"
                or not origin.hostname
                or self._is_local_origin_hostname(origin.hostname)
                for origin in parsed_origins
            ):
                invalid_fields.append("cors_allowed_origins")
        if invalid_fields:
            joined_fields = ", ".join(sorted(set(invalid_fields)))
            raise ValueError(f"Unsafe {self.app_env} settings: {joined_fields}")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    获取进程内缓存的应用配置。

    输入：无。

    输出：Settings，当前进程使用的配置对象。
    """
    return Settings()
