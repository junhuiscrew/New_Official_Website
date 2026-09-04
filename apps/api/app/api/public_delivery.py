"""Sitemap、Robots 与可选 llms.txt 的根路径公开端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.modules.content.services.indexable import list_indexable_routes
from app.modules.discovery.sitemap import OFFICIAL_ORIGIN, SitemapEntry, render_sitemap

router = APIRouter(tags=["discovery-files"])


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml(session: AsyncSession = Depends(get_session)) -> Response:
    """
    从统一严格可索引路由源生成 Sitemap。

    输入：session，请求数据库会话。
    输出：Response，XML Sitemap；关闭开关时返回 404。
    """
    settings = get_settings()
    if not settings.public_sitemap_enabled:
        return Response(status_code=404)
    routes = await list_indexable_routes(session)
    xml = render_sitemap([SitemapEntry(route.path, route.updated_at) for route in routes])
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> Response:
    """
    按环境输出抓取规则，并始终声明正式 Sitemap。

    输入：运行时环境配置。
    输出：Response，纯文本 robots 规则。
    """
    settings = get_settings()
    if settings.app_env != "production":
        content = "User-agent: *\nDisallow: /\n"
    else:
        content = (
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /admin/\n"
            "Disallow: /preview/\n"
            "Disallow: /api/v1/rfq/\n"
            f"Sitemap: {OFFICIAL_ORIGIN}/sitemap.xml\n"
        )
    return Response(content=content, media_type="text/plain", headers={"X-Robots-Tag": "noindex"})


@router.get("/llms.txt", include_in_schema=False)
async def llms_txt(session: AsyncSession = Depends(get_session)) -> Response:
    """
    可选输出已发布 canonical 内容清单，不包含隐藏 GEO 事实。

    输入：session，请求数据库会话。
    输出：Response，面向工具的纯文本公开 URL 清单。
    """
    settings = get_settings()
    if not settings.llms_txt_enabled:
        return Response(status_code=404)
    routes = await list_indexable_routes(session)
    lines = ["# Junhui Global Website", "", "Canonical public resources:"]
    lines.extend(f"- {OFFICIAL_ORIGIN}{route.path}" for route in routes)
    return Response(content="\n".join(lines) + "\n", media_type="text/plain", headers={"X-Robots-Tag": "noindex"})
