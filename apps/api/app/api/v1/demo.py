"""Demo R2 后台专用 API，只在显式演示实例中开放。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.responses import ApiResponse, success_response
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.demo.presentation import (
    DemoPresentationMediaUpdate,
    get_demo_presentation_media,
    update_demo_presentation_media,
)
from app.modules.users.models import User

router = APIRouter(prefix="/demo-r2", tags=["demo-r2"])


@router.get("/presentation-media", response_model=ApiResponse[dict])
async def demo_presentation_media(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("media.read")),
) -> ApiResponse[dict]:
    """返回可读文件名驱动的Demo首页媒体选择，不向编辑人员暴露对象存储路径。"""
    return success_response(await get_demo_presentation_media(session))


@router.put("/presentation-media", response_model=ApiResponse[dict])
async def save_demo_presentation_media(
    payload: DemoPresentationMediaUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("media.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict]:
    """保存固定媒体槽位，使用登录权限、CSRF、并发令牌和Audit。"""
    return success_response(
        await update_demo_presentation_media(session, payload=payload, actor_id=user.id)
    )
