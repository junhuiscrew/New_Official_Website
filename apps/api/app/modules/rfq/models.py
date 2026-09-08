"""RFQ 多项目、私有文件和安全状态模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin


class RFQ(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """客户询盘主实体；公开接口只返回 public_reference。"""

    __tablename__ = "rfqs"
    __table_args__ = (
        CheckConstraint("status IN ('new','qualified','in_progress','waiting_customer','quoted','won','lost','spam','closed')", name="rfq_status_value"),
        CheckConstraint("priority IN ('low','normal','high','urgent')", name="rfq_priority_value"),
        CheckConstraint(
            "((privacy_notice_version_id IS NULL AND privacy_version_label IS NULL "
            "AND privacy_policy_locale IS NULL AND privacy_content_hash IS NULL "
            "AND privacy_canonical_url IS NULL AND privacy_confirmed_at IS NULL) OR "
            "(privacy_notice_version_id IS NOT NULL AND privacy_version_label IS NOT NULL "
            "AND privacy_policy_locale IS NOT NULL AND privacy_content_hash IS NOT NULL "
            "AND privacy_canonical_url IS NOT NULL AND privacy_confirmed_at IS NOT NULL))",
            name="rfq_privacy_metadata_all_or_none",
        ),
        {"comment": "客户询盘表"},
    )

    public_reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, comment="公开询盘编号，不是内部UUID")
    status: Mapped[str] = mapped_column(String(32), default="new", server_default="new", nullable=False, comment="询盘状态")
    priority: Mapped[str] = mapped_column(String(16), default="normal", server_default="normal", nullable=False, comment="优先级")
    company_name: Mapped[str] = mapped_column(String(240), nullable=False, comment="公司名称")
    contact_name: Mapped[str] = mapped_column(String(160), nullable=False, comment="联系人")
    email: Mapped[str] = mapped_column(String(320), nullable=False, comment="标准化邮箱")
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="电话")
    whatsapp: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="WhatsApp")
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, comment="国家代码")
    website: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="公司网站")
    message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="询盘留言")
    preferred_language: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="偏好语言")
    source_page_url: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="来源页面URL")
    source_owner_type: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="来源实体类型")
    source_owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="来源实体ID")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="分配销售用户ID")
    submitted_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="提交IP，受控审计字段")
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="提交User-Agent")
    consent_privacy: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="隐私同意")
    consent_marketing: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, comment="营销同意")
    privacy_notice_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("privacy_notice_versions.id", ondelete="RESTRICT"),
        nullable=True,
        comment="确认时不可变隐私政策版本ID；历史询盘为空",
    )
    privacy_version_label: Mapped[str | None] = mapped_column(
        String(40), nullable=True, comment="确认时公开隐私政策版本标签；历史询盘为空"
    )
    privacy_policy_locale: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="确认时隐私政策语言；历史询盘为空"
    )
    privacy_content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="确认时隐私政策内容哈希；历史询盘为空"
    )
    privacy_canonical_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="确认时隐私政策规范URL；历史询盘为空"
    )
    privacy_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="服务端确认隐私政策上下文时间；历史询盘为空"
    )
    spam_score: Mapped[float | None] = mapped_column(nullable=True, comment="垃圾评分")


class RFQItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """一个 RFQ 下的结构化询盘项目。"""

    __tablename__ = "rfq_items"
    __table_args__ = (CheckConstraint("item_type IN ('product','screw','barrel','component','custom','other')", name="rfq_item_type_value"), {"comment": "询盘项目表"})

    rfq_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False, comment="询盘ID")
    item_type: Mapped[str] = mapped_column(String(24), nullable=False, comment="项目类型")
    product_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True, comment="产品ID")
    product_model_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_models.id", ondelete="SET NULL"), nullable=True, comment="产品型号ID")
    product_name_text: Mapped[str | None] = mapped_column(String(240), nullable=True, comment="客户填写产品名称")
    quantity: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="数量")
    material_text: Mapped[str | None] = mapped_column(String(240), nullable=True, comment="材料描述")
    screw_diameter: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="螺杆直径")
    length: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="长度")
    machine_brand: Mapped[str | None] = mapped_column(String(160), nullable=True, comment="设备品牌")
    machine_model: Mapped[str | None] = mapped_column(String(160), nullable=True, comment="设备型号")
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True, comment="定制要求")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False, comment="项目排序")


class RFQFile(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """询盘私有附件；必须引用 private-rfq 媒体。"""

    __tablename__ = "rfq_files"
    __table_args__ = (CheckConstraint("file_category IN ('drawing','cad','photo','pdf','specification','other')", name="rfq_file_category_value"), {"comment": "询盘私有文件表"})

    rfq_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False, comment="询盘ID")
    rfq_item_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("rfq_items.id", ondelete="SET NULL"), nullable=True, comment="关联项目ID")
    media_asset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=False, comment="私有媒体ID")
    file_category: Mapped[str] = mapped_column(String(32), nullable=False, comment="文件分类")
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False, comment="原始文件名")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="文件SHA256")
    uploaded_at: Mapped[str | None] = mapped_column(String(40), nullable=True, comment="上传时间")

