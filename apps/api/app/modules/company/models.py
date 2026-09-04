"""Company Trust 结构化模型：公司、能力、设备、证书、专利、荣誉与展会。"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin

_JSON = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")
_STATUS = "status IN ('enabled','disabled','retired')"


class CompanyProfile(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """公司公开档案；真实字段由管理员维护。"""

    __tablename__ = "company_profiles"
    __table_args__ = (CheckConstraint(_STATUS, name="company_profile_status_value"), {"comment": "公司公开档案表"})

    status: Mapped[str] = mapped_column(String(16), default="enabled", server_default="enabled", nullable=False, comment="状态：enabled启用，disabled停用，retired退役")
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="成立年份")
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="从业年限")
    employee_count_range: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="员工数量范围")
    factory_area_sqm: Mapped[float | None] = mapped_column(nullable=True, comment="厂房面积平方米")
    annual_capacity_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="年产能描述")
    export_markets_json: Mapped[list[str] | None] = mapped_column(_JSON, nullable=True, comment="出口市场JSON数组")
    public_phone: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="公开电话")
    public_email: Mapped[str | None] = mapped_column(String(320), nullable=True, comment="公开邮箱")
    public_address: Mapped[str | None] = mapped_column(Text, nullable=True, comment="公开地址")
    latitude: Mapped[float | None] = mapped_column(nullable=True, comment="公开纬度")
    longitude: Mapped[float | None] = mapped_column(nullable=True, comment="公开经度")
    logo_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="公司Logo媒体ID")
    primary_factory_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="主工厂媒体ID")


class CompanyProfileTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """公司档案多语言公开正文。"""

    __tablename__ = "company_profile_translations"
    __table_args__ = (UniqueConstraint("company_profile_id", "locale_id", name="uq_company_profile_translation_locale"), {"comment": "公司档案翻译表"})

    company_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False, comment="公司档案ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    company_name: Mapped[str] = mapped_column(String(240), nullable=False, comment="公司名称")
    short_intro: Mapped[str] = mapped_column(Text, nullable=False, comment="公司简短介绍")
    full_intro: Mapped[str] = mapped_column(Text, nullable=False, comment="公司完整介绍")
    mission: Mapped[str | None] = mapped_column(Text, nullable=True, comment="使命")
    advantages_json: Mapped[list[str] | None] = mapped_column(_JSON, nullable=True, comment="公司优势JSON数组")


class ManufacturingCapability(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """制造能力结构化主实体。"""

    __tablename__ = "manufacturing_capabilities"
    __table_args__ = (CheckConstraint(_STATUS, name="manufacturing_capability_status_value"), {"comment": "制造能力表"})

    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, comment="稳定能力Slug")
    capability_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="能力类型")
    status: Mapped[str] = mapped_column(String(16), default="enabled", server_default="enabled", nullable=False, comment="状态")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False, comment="排序")
    primary_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="主媒体ID")


class ManufacturingCapabilityTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """制造能力翻译。"""

    __tablename__ = "manufacturing_capability_translations"
    __table_args__ = (UniqueConstraint("capability_id", "locale_id", name="uq_capability_translation_locale"), {"comment": "制造能力翻译表"})

    capability_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("manufacturing_capabilities.id", ondelete="CASCADE"), nullable=False, comment="能力ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    name: Mapped[str] = mapped_column(String(240), nullable=False, comment="能力名称")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="能力摘要")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="能力描述")
    key_facts_json: Mapped[list[str] | None] = mapped_column(_JSON, nullable=True, comment="关键事实JSON数组")


class Equipment(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """设备结构化实体；V1 不建立独立公开路由。"""

    __tablename__ = "equipment"
    __table_args__ = (CheckConstraint(_STATUS, name="equipment_status_value"), {"comment": "设备表"})

    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, comment="稳定设备Slug")
    equipment_type: Mapped[str] = mapped_column(String(80), nullable=False, comment="设备类型")
    manufacturer: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="制造商")
    model: Mapped[str | None] = mapped_column(String(160), nullable=True, comment="设备型号")
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="设备数量")
    commissioning_year: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="投产年份")
    precision_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="精度描述")
    capacity_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="能力描述")
    status: Mapped[str] = mapped_column(String(16), default="enabled", server_default="enabled", nullable=False, comment="状态")
    featured: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, comment="是否推荐")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False, comment="排序")
    primary_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="主媒体ID")


class EquipmentTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """设备翻译。"""

    __tablename__ = "equipment_translations"
    __table_args__ = (UniqueConstraint("equipment_id", "locale_id", name="uq_equipment_translation_locale"), {"comment": "设备翻译表"})

    equipment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, comment="设备ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    name: Mapped[str] = mapped_column(String(240), nullable=False, comment="设备名称")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="设备摘要")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="设备描述")
    public_specs_json: Mapped[dict | None] = mapped_column(_JSON, nullable=True, comment="公开规格JSON")


def _simple_entity(name: str, table: str, comment: str) -> type[Base]:
    """构造 Trust 简单主实体模型。"""
    return type(name, (UuidPrimaryKeyMixin, TimestampMixin, Base), {
        "__tablename__": table,
        "__table_args__": (CheckConstraint(_STATUS, name=f"{table}_status_value"), {"comment": comment}),
        "slug": mapped_column(String(160), unique=True, nullable=False, comment="稳定Slug"),
        "status": mapped_column(String(16), default="enabled", server_default="enabled", nullable=False, comment="状态：enabled启用，disabled停用，retired退役"),
        "sort_order": mapped_column(Integer, default=0, server_default="0", nullable=False, comment="排序"),
        "primary_media_id": mapped_column(Uuid(as_uuid=True), nullable=True, comment="主媒体ID"),
    })


Certificate = _simple_entity("Certificate", "certificates", "证书表")
Patent = _simple_entity("Patent", "patents", "专利表")
Honor = _simple_entity("Honor", "honors", "荣誉表")
Exhibition = _simple_entity("Exhibition", "exhibitions", "展会表")

# 证书、专利和荣誉需要的事实字段独立追加，避免把可信事实塞进富文本。
Certificate.certificate_type = mapped_column(String(80), nullable=False, default="other", comment="证书类型")
Certificate.certificate_number = mapped_column(String(160), nullable=True, comment="证书编号")
Certificate.issuer = mapped_column(String(240), nullable=False, default="", comment="颁发机构")
Certificate.issue_date = mapped_column(Date, nullable=True, comment="颁发日期")
Certificate.expiry_date = mapped_column(Date, nullable=True, comment="到期日期")
Certificate.verification_url = mapped_column(String(800), nullable=True, comment="验证URL")
Certificate.public_file_media_id = mapped_column(Uuid(as_uuid=True), nullable=True, comment="公开证书文件媒体ID")
Patent.patent_number = mapped_column(String(160), nullable=False, default="", comment="专利号")
Patent.patent_type = mapped_column(String(80), nullable=False, default="other", comment="专利类型")
Patent.application_number = mapped_column(String(160), nullable=True, comment="申请号")
Patent.filing_date = mapped_column(Date, nullable=True, comment="申请日期")
Patent.grant_date = mapped_column(Date, nullable=True, comment="授权日期")
Patent.jurisdiction = mapped_column(String(80), nullable=True, comment="司法辖区")
Patent.inventor_text = mapped_column(Text, nullable=True, comment="发明人描述")
Patent.verification_url = mapped_column(String(800), nullable=True, comment="验证URL")
Patent.public_file_media_id = mapped_column(Uuid(as_uuid=True), nullable=True, comment="公开专利文件媒体ID")
Honor.issuing_organization = mapped_column(String(240), nullable=False, default="", comment="颁发组织")
Honor.award_date = mapped_column(Date, nullable=True, comment="获奖日期")
Exhibition.event_name = mapped_column(String(240), nullable=False, default="", comment="展会名称")
Exhibition.country_code = mapped_column(String(2), nullable=True, comment="国家代码")
Exhibition.city = mapped_column(String(120), nullable=True, comment="城市")
Exhibition.start_date = mapped_column(Date, nullable=True, comment="开始日期")
Exhibition.end_date = mapped_column(Date, nullable=True, comment="结束日期")
Exhibition.booth_no = mapped_column(String(80), nullable=True, comment="展位号")


def _translation(name: str, table: str, parent: str, parent_table: str, fields: dict[str, object], comment: str) -> type[Base]:
    """构造 Trust 翻译表。"""
    attrs: dict[str, object] = {
        "__tablename__": table,
        "__table_args__": (UniqueConstraint(parent, "locale_id", name=f"uq_{table}_locale"), {"comment": comment}),
        parent: mapped_column(Uuid(as_uuid=True), ForeignKey(f"{parent_table}.id", ondelete="CASCADE"), nullable=False, comment="主实体ID"),
        "locale_id": mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID"),
    }
    attrs.update(fields)
    return type(name, (UuidPrimaryKeyMixin, TimestampMixin, Base), attrs)


CertificateTranslation = _translation("CertificateTranslation", "certificate_translations", "certificate_id", "certificates", {"name": mapped_column(String(240), nullable=False, comment="证书名称"), "summary": mapped_column(Text, nullable=True, comment="证书摘要"), "scope": mapped_column(Text, nullable=True, comment="证书范围")}, "证书翻译表")
PatentTranslation = _translation("PatentTranslation", "patent_translations", "patent_id", "patents", {"title": mapped_column(String(240), nullable=False, comment="专利标题"), "summary": mapped_column(Text, nullable=True, comment="专利摘要"), "technical_scope": mapped_column(Text, nullable=True, comment="技术范围")}, "专利翻译表")
HonorTranslation = _translation("HonorTranslation", "honor_translations", "honor_id", "honors", {"title": mapped_column(String(240), nullable=False, comment="荣誉标题"), "summary": mapped_column(Text, nullable=True, comment="荣誉摘要")}, "荣誉翻译表")
ExhibitionTranslation = _translation("ExhibitionTranslation", "exhibition_translations", "exhibition_id", "exhibitions", {"title": mapped_column(String(240), nullable=False, comment="展会标题"), "summary": mapped_column(Text, nullable=True, comment="展会摘要"), "description": mapped_column(Text, nullable=True, comment="展会描述")}, "展会翻译表")


def _relation(name: str, table: str, left: str, left_table: str, right: str, right_table: str) -> type[Base]:
    """构造带排序与备注的显式 Trust 关系。"""
    return type(name, (Base,), {
        "__tablename__": table,
        "__table_args__": {"comment": f"{table} 显式关系表"},
        left: mapped_column(Uuid(as_uuid=True), ForeignKey(f"{left_table}.id", ondelete="CASCADE"), primary_key=True, comment="左侧实体ID"),
        right: mapped_column(Uuid(as_uuid=True), ForeignKey(f"{right_table}.id", ondelete="CASCADE"), primary_key=True, comment="右侧实体ID"),
        "sort_order": mapped_column(Integer, default=0, server_default="0", nullable=False, comment="关系排序"),
        "notes": mapped_column(Text, nullable=True, comment="关系备注"),
    })


CapabilityEquipment = _relation("CapabilityEquipment", "capability_equipment", "capability_id", "manufacturing_capabilities", "equipment_id", "equipment")
CapabilityCertificate = _relation("CapabilityCertificate", "capability_certificates", "capability_id", "manufacturing_capabilities", "certificate_id", "certificates")
CapabilityPatent = _relation("CapabilityPatent", "capability_patents", "capability_id", "manufacturing_capabilities", "patent_id", "patents")
TechnologyEquipment = _relation("TechnologyEquipment", "technology_equipment", "technology_id", "technologies", "equipment_id", "equipment")

TRUST_ENTITY_MODELS = (CompanyProfile, ManufacturingCapability, Equipment, Certificate, Patent, Honor, Exhibition)
TRUST_TRANSLATION_MODELS = (CompanyProfileTranslation, ManufacturingCapabilityTranslation, EquipmentTranslation, CertificateTranslation, PatentTranslation, HonorTranslation, ExhibitionTranslation)
TRUST_RELATION_MODELS = (CapabilityEquipment, CapabilityCertificate, CapabilityPatent, TechnologyEquipment)
