"""正式主域 Sitemap XML 生成器。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from xml.sax.saxutils import escape

OFFICIAL_ORIGIN = "https://junhuiscrewbarrel.com"


@dataclass(frozen=True)
class SitemapEntry:
    """Sitemap 的 canonical 路径与真实更新时间。"""

    path: str
    last_modified: datetime


def render_sitemap(entries: list[SitemapEntry]) -> str:
    """
    将严格筛选后的 canonical 路由渲染为 Sitemap XML。

    输入：entries，包含站内路径和真实更新时间的项目。
    输出：str，符合 sitemap 协议的 XML。
    """
    urls = "".join(
        "<url>"
        f"<loc>{escape(OFFICIAL_ORIGIN + entry.path)}</loc>"
        f"<lastmod>{entry.last_modified.isoformat()}</lastmod>"
        "</url>"
        for entry in entries
    )
    return '<?xml version="1.0" encoding="UTF-8"?>' + (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )
