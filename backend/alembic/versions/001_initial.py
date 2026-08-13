"""initial schema — no auth

Revision ID: 001_initial
Revises:
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # companies
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tax_code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(500)),
        sa.Column("address", sa.Text()),
        sa.Column("representative", sa.String(255)),
        sa.Column("industry", sa.String(255)),
        sa.Column("status", sa.String(50)),
        sa.Column("raw_data", postgresql.JSONB()),
        sa.Column("enrichment_status", sa.String(50), server_default="pending"),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tax_code", name="uq_companies_tax_code"),
    )
    op.create_index("ix_companies_tax_code", "companies", ["tax_code"])

    # site_visits
    op.create_table(
        "site_visits",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by", sa.String(100)),          # tên người tạo, không bắt buộc
        sa.Column("visit_date", sa.DateTime(timezone=True)),
        sa.Column("visit_type", sa.String(50), nullable=False, server_default="standard"),
        sa.Column("status", sa.String(50), nullable=False, server_default="in_progress"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_site_visits_company_id", "site_visits", ["company_id"])

    # visit_photos
    op.create_table(
        "visit_photos",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("visit_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("site_visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger()),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("gdrive_file_id", sa.String(255)),
        sa.Column("gdrive_url", sa.Text()),
        sa.Column("gdrive_folder", sa.Text()),
        sa.Column("photo_type", sa.String(100)),
        sa.Column("is_required_type", sa.Boolean()),
        sa.Column("processing_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("sonnet_description", sa.Text()),
        sa.Column("gpt4_description", sa.Text()),
        sa.Column("opus_description", sa.Text()),
        sa.Column("final_description", sa.Text()),
        sa.Column("ocr_text", sa.Text()),
        sa.Column("ocr_layout", postgresql.JSONB()),
        sa.Column("models_agreed", sa.Boolean()),
        sa.Column("confidence_score", sa.Float()),
        sa.Column("comparison_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_visit_photos_visit_id", "visit_photos", ["visit_id"])

    # conversations
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("visit_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("site_visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_conversations_visit_id", "conversations", ["visit_id"])

    # messages
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("image_urls", postgresql.JSONB()),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # skill_files
    op.create_table(
        "skill_files",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("visit_type", postgresql.ARRAY(sa.String())),
        sa.Column("content", sa.Text()),
        sa.Column("file_path", sa.String(500)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # required_photo_types
    op.create_table(
        "required_photo_types",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("visit_type", sa.String(50), nullable=False),
        sa.Column("photo_type", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("visit_type", "photo_type", name="uq_visit_type_photo_type"),
    )
    op.create_index("ix_required_photo_types_visit_type", "required_photo_types", ["visit_type"])

    # processing_jobs
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("photo_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("visit_photos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("celery_task_id", sa.String(255)),
        sa.Column("error_message", sa.Text()),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_processing_jobs_photo_id", "processing_jobs", ["photo_id"])

    # Seed required photo types
    op.execute("""
        INSERT INTO required_photo_types (id, visit_type, photo_type, description, is_mandatory, order_index) VALUES
          (gen_random_uuid(), 'standard',  'biển_hiệu',            'Biển hiệu công ty bên ngoài',      true, 1),
          (gen_random_uuid(), 'standard',  'mặt_tiền',             'Mặt tiền tòa nhà / văn phòng',     true, 2),
          (gen_random_uuid(), 'standard',  'khu_vực_làm_việc',     'Khu vực làm việc nội thất',        true, 3),
          (gen_random_uuid(), 'standard',  'giấy_phép_kinh_doanh', 'Giấy phép kinh doanh',             true, 4),
          (gen_random_uuid(), 'factory',   'biển_hiệu',            'Biển hiệu nhà máy',                true, 1),
          (gen_random_uuid(), 'factory',   'mặt_tiền',             'Cổng / mặt tiền nhà máy',          true, 2),
          (gen_random_uuid(), 'factory',   'dây_chuyền_sản_xuất',  'Dây chuyền / máy móc sản xuất',    true, 3),
          (gen_random_uuid(), 'factory',   'kho_nguyên_liệu',      'Kho nguyên liệu đầu vào',          true, 4),
          (gen_random_uuid(), 'factory',   'kho_thành_phẩm',       'Kho thành phẩm đầu ra',            true, 5),
          (gen_random_uuid(), 'factory',   'giấy_phép_kinh_doanh', 'Giấy phép kinh doanh',             true, 6),
          (gen_random_uuid(), 'warehouse', 'biển_hiệu',            'Biển hiệu kho',                    true, 1),
          (gen_random_uuid(), 'warehouse', 'mặt_tiền',             'Cổng / mặt tiền kho',              true, 2),
          (gen_random_uuid(), 'warehouse', 'kho',                  'Bên trong kho (hàng hóa, kệ)',     true, 3),
          (gen_random_uuid(), 'warehouse', 'giấy_phép_kinh_doanh', 'Giấy phép kinh doanh',             true, 4)
        ON CONFLICT DO NOTHING;
    """)


def downgrade():
    for t in ["processing_jobs", "required_photo_types", "skill_files",
              "messages", "conversations", "visit_photos", "site_visits", "companies"]:
        op.drop_table(t)
