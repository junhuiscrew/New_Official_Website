"""创建 RFQ、多项目和私有附件基础表。"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260904_0009"
down_revision = "20260904_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> tuple[sa.Column, sa.Column]:
    """统一时间字段。"""
    return (sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment="创建时间"), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment="更新时间"))


def upgrade() -> None:
    """创建询盘、项目和私有文件表。"""
    op.create_table("rfqs", sa.Column("id", sa.Uuid(), primary_key=True, comment="主键ID"), sa.Column("public_reference", sa.String(40), unique=True, nullable=False, comment="公开询盘编号"), sa.Column("status", sa.String(32), nullable=False, server_default="new", comment="询盘状态"), sa.Column("priority", sa.String(16), nullable=False, server_default="normal", comment="优先级"), sa.Column("company_name", sa.String(240), nullable=False, comment="公司名称"), sa.Column("contact_name", sa.String(160), nullable=False, comment="联系人"), sa.Column("email", sa.String(320), nullable=False, comment="标准化邮箱"), sa.Column("phone", sa.String(80), nullable=True, comment="电话"), sa.Column("whatsapp", sa.String(80), nullable=True, comment="WhatsApp"), sa.Column("country_code", sa.String(2), nullable=True, comment="国家代码"), sa.Column("website", sa.String(500), nullable=True, comment="网站"), sa.Column("message", sa.Text(), nullable=True, comment="留言"), sa.Column("preferred_language", sa.String(32), nullable=True, comment="偏好语言"), sa.Column("source_page_url", sa.String(1000), nullable=True, comment="来源页面"), sa.Column("source_owner_type", sa.String(100), nullable=True, comment="来源实体类型"), sa.Column("source_owner_id", sa.Uuid(), nullable=True, comment="来源实体ID"), sa.Column("assigned_to", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="销售用户ID"), sa.Column("submitted_ip", sa.String(64), nullable=True, comment="提交IP"), sa.Column("user_agent", sa.String(500), nullable=True, comment="User-Agent"), sa.Column("consent_privacy", sa.Boolean(), nullable=False, comment="隐私同意"), sa.Column("consent_marketing", sa.Boolean(), nullable=False, server_default=sa.false(), comment="营销同意"), sa.Column("spam_score", sa.Float(), nullable=True, comment="垃圾评分"), *_ts(), sa.CheckConstraint("status IN ('new','qualified','in_progress','waiting_customer','quoted','won','lost','spam','closed')", name="rfq_status_value"), sa.CheckConstraint("priority IN ('low','normal','high','urgent')", name="rfq_priority_value"), comment="客户询盘表")
    op.create_table("rfq_items", sa.Column("id", sa.Uuid(), primary_key=True, comment="主键ID"), sa.Column("rfq_id", sa.Uuid(), sa.ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False, comment="询盘ID"), sa.Column("item_type", sa.String(24), nullable=False, comment="项目类型"), sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True, comment="产品ID"), sa.Column("product_model_id", sa.Uuid(), sa.ForeignKey("product_models.id", ondelete="SET NULL"), nullable=True, comment="产品型号ID"), sa.Column("product_name_text", sa.String(240), nullable=True, comment="产品名称"), sa.Column("quantity", sa.String(80), nullable=True, comment="数量"), sa.Column("material_text", sa.String(240), nullable=True, comment="材料"), sa.Column("screw_diameter", sa.String(80), nullable=True, comment="直径"), sa.Column("length", sa.String(80), nullable=True, comment="长度"), sa.Column("machine_brand", sa.String(160), nullable=True, comment="设备品牌"), sa.Column("machine_model", sa.String(160), nullable=True, comment="设备型号"), sa.Column("requirements", sa.Text(), nullable=True, comment="要求"), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="排序"), *_ts(), sa.CheckConstraint("item_type IN ('product','screw','barrel','component','custom','other')", name="rfq_item_type_value"), comment="询盘项目表")
    op.create_table("rfq_files", sa.Column("id", sa.Uuid(), primary_key=True, comment="主键ID"), sa.Column("rfq_id", sa.Uuid(), sa.ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False, comment="询盘ID"), sa.Column("rfq_item_id", sa.Uuid(), sa.ForeignKey("rfq_items.id", ondelete="SET NULL"), nullable=True, comment="项目ID"), sa.Column("media_asset_id", sa.Uuid(), sa.ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=False, comment="私有媒体ID"), sa.Column("file_category", sa.String(32), nullable=False, comment="文件分类"), sa.Column("original_filename", sa.String(500), nullable=False, comment="原始文件名"), sa.Column("sha256", sa.String(64), nullable=False, comment="SHA256"), sa.Column("uploaded_at", sa.String(40), nullable=True, comment="上传时间"), *_ts(), sa.CheckConstraint("file_category IN ('drawing','cad','photo','pdf','specification','other')", name="rfq_file_category_value"), comment="询盘私有文件表")


def downgrade() -> None:
    """按依赖逆序删除 RFQ 表。"""
    op.drop_table("rfq_files")
    op.drop_table("rfq_items")
    op.drop_table("rfqs")

