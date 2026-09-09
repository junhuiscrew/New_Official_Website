"""测试用途：锁定媒体后台重开时所需的可读双语详情。"""

from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.media import _media_detail_dto


def test_media_detail_dto_contains_public_fields_and_localized_metadata() -> None:
    """
    验证媒体详情 DTO 可供 Admin 重开已保存元数据。

    输入：虚构媒体、语言及双语翻译对象。
    输出：断言公开字段与按语言组织的 Alt、标题和图注均被保留。
    """
    asset_id = uuid4()
    zh_id = uuid4()
    en_id = uuid4()
    asset = SimpleNamespace(
        id=asset_id,
        media_type="image",
        original_filename="demo-screw.jpg",
        visibility="public",
        mime_type="image/jpeg",
        file_extension="jpg",
        file_size_bytes=1024,
        width=1200,
        height=900,
        duration_seconds=None,
        upload_status="ready",
    )
    locales = [
        SimpleNamespace(id=zh_id, code="zh-CN", native_name="简体中文"),
        SimpleNamespace(id=en_id, code="en", native_name="English"),
    ]
    translations = [
        SimpleNamespace(
            locale_id=zh_id,
            alt_text="耐磨螺杆近景示意",
            title="耐磨螺杆",
            caption="DEMO 示意素材",
        )
    ]

    result = _media_detail_dto(asset, translations, locales)

    assert result["id"] == str(asset_id)
    assert result["translations"][0] == {
        "locale_id": str(zh_id),
        "locale_code": "zh-CN",
        "locale_name": "简体中文",
        "alt_text": "耐磨螺杆近景示意",
        "title": "耐磨螺杆",
        "caption": "DEMO 示意素材",
    }
    assert result["translations"][1]["alt_text"] == ""
