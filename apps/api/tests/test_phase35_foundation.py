"""Phase 3.5 Trust、Media 与 RFQ 安全契约测试。"""

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.core.exceptions.handlers import AppException
from app.modules.media.services import sanitize_filename, validate_upload_bytes
from app.modules.media.storage import private_url_expiry
from app.modules.rfq.schemas import RFQCreate


def _encoded_image(image_format: str, size: tuple[int, int]) -> bytes:
    """
    构造可被 Pillow 完整解码的测试图片。

    输入：image_format 图片格式；size 预期像素宽高。
    输出：bytes，内存编码后的真实图片内容。
    """
    output = io.BytesIO()
    Image.new("RGB", size, (20, 80, 140)).save(output, image_format)
    return output.getvalue()


def test_phase35_tables_registered_with_chinese_comments() -> None:
    """验证 Trust、Media、Download、RFQ 表均注册且字段有中文说明。"""
    expected = {
        "company_profiles", "company_profile_translations", "manufacturing_capabilities", "manufacturing_capability_translations",
        "equipment", "equipment_translations", "certificates", "certificate_translations", "patents", "patent_translations",
        "honors", "honor_translations", "exhibitions", "exhibition_translations", "capability_equipment", "technology_equipment",
        "media_assets", "media_asset_translations", "download_resources", "download_resource_translations", "rfqs", "rfq_items", "rfq_files",
    }
    from app.core.database import Base
    assert expected.issubset(Base.metadata.tables)
    for table_name in expected:
        assert all(column.comment for column in Base.metadata.tables[table_name].columns), table_name


def test_public_and_private_storage_boundary() -> None:
    """公开文件只能走 public-media，RFQ 文件扩展名允许 CAD。"""
    public = validate_upload_bytes("factory.png", "image/png", _encoded_image("PNG", (32, 18)))
    private = validate_upload_bytes("drawing.step", "application/step", b"ISO-10303-21;", private=True)
    assert public["media_type"] == "image"
    assert (public["width"], public["height"]) == (32, 18)
    assert private["media_type"] == "cad"
    with pytest.raises(AppException):
        validate_upload_bytes("drawing.step", "application/step", b"ISO-10303-21")


def test_image_upload_decodes_dimensions_and_rejects_signature_only_payload() -> None:
    """图片宽高必须来自真实解码，只有合法文件头的损坏内容不能入库。"""
    metadata = validate_upload_bytes(
        "product.webp",
        "image/webp",
        _encoded_image("WEBP", (73, 41)),
    )

    assert (metadata["width"], metadata["height"]) == (73, 41)
    with pytest.raises(AppException) as raised:
        validate_upload_bytes("broken.webp", "image/webp", b"RIFFbrokenWEBPpayload")
    assert raised.value.code == "image_decode_failed"


def test_upload_rejects_double_extension_and_mime_spoof() -> None:
    """验证危险双扩展名和 MIME 伪造被拒绝。"""
    with pytest.raises(AppException):
        validate_upload_bytes("photo.jpg.exe", "image/jpeg", b"\xff\xd8\xff")
    with pytest.raises(AppException):
        validate_upload_bytes("photo.jpg", "image/png", b"\xff\xd8\xff")


def test_filename_sanitization_and_private_url_ttl() -> None:
    """验证路径遍历文件名清洗与私有链接短 TTL 边界。"""
    assert sanitize_filename("../../客户 图纸.step") == "step"
    expires = private_url_expiry(3600)
    assert 590 <= (expires.timestamp() - __import__("datetime").datetime.now(__import__("datetime").UTC).timestamp()) <= 910


def test_public_rfq_response_input_has_no_internal_fields() -> None:
    """验证公共 RFQ 输入只包含公开表单字段，且隐私同意必填。"""
    payload = RFQCreate(company_name="ACME", contact_name="Lee", email="Lee@Example.com", message="Need a quote", consent_privacy=True)
    assert str(payload.email) == "lee@example.com"
    assert "assigned_to" not in payload.model_dump()
    with pytest.raises(ValueError):
        RFQCreate(company_name="ACME", contact_name="Lee", email="lee@example.com", consent_privacy=False)
