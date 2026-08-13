"""
SQLAlchemy ORM models — không có auth, không có users table.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# companies
# ─────────────────────────────────────────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tax_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(500))
    address: Mapped[Optional[str]] = mapped_column(Text)
    representative: Mapped[Optional[str]] = mapped_column(String(255))
    industry: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    enrichment_status: Mapped[str] = mapped_column(String(50), default="pending")
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    site_visits: Mapped[List["SiteVisit"]] = relationship(back_populates="company")


# ─────────────────────────────────────────────────────────────────────────────
# site_visits
# ─────────────────────────────────────────────────────────────────────────────

class SiteVisit(Base):
    __tablename__ = "site_visits"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Không có user_id — ai cũng xem được
    created_by: Mapped[Optional[str]] = mapped_column(String(100))  # tên người tạo, tự điền
    visit_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    visit_type: Mapped[str] = mapped_column(String(50), nullable=False, default="standard")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="in_progress")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="site_visits")
    photos: Mapped[List["VisitPhoto"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────────────
# visit_photos
# ─────────────────────────────────────────────────────────────────────────────

class VisitPhoto(Base):
    __tablename__ = "visit_photos"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    visit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("site_visits.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    gdrive_file_id: Mapped[Optional[str]] = mapped_column(String(255))
    gdrive_url: Mapped[Optional[str]] = mapped_column(Text)
    gdrive_folder: Mapped[Optional[str]] = mapped_column(Text)

    photo_type: Mapped[Optional[str]] = mapped_column(String(100))
    is_required_type: Mapped[Optional[bool]] = mapped_column(Boolean)
    processing_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    sonnet_description: Mapped[Optional[str]] = mapped_column(Text)
    gpt4_description: Mapped[Optional[str]] = mapped_column(Text)
    opus_description: Mapped[Optional[str]] = mapped_column(Text)
    final_description: Mapped[Optional[str]] = mapped_column(Text)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text)
    ocr_layout: Mapped[Optional[dict]] = mapped_column(JSONB)

    models_agreed: Mapped[Optional[bool]] = mapped_column(Boolean)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    comparison_notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    visit: Mapped["SiteVisit"] = relationship(back_populates="photos")
    processing_jobs: Mapped[List["ProcessingJob"]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────────────
# conversations
# ─────────────────────────────────────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    visit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("site_visits.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    visit: Mapped["SiteVisit"] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


# ─────────────────────────────────────────────────────────────────────────────
# messages
# ─────────────────────────────────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_urls: Mapped[Optional[list]] = mapped_column(JSONB)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


# ─────────────────────────────────────────────────────────────────────────────
# skill_files
# ─────────────────────────────────────────────────────────────────────────────

class SkillFile(Base):
    __tablename__ = "skill_files"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    visit_type: Mapped[Optional[list]] = mapped_column(ARRAY(String))
    content: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ─────────────────────────────────────────────────────────────────────────────
# required_photo_types
# ─────────────────────────────────────────────────────────────────────────────

class RequiredPhotoType(Base):
    __tablename__ = "required_photo_types"
    __table_args__ = (
        UniqueConstraint("visit_type", "photo_type", name="uq_visit_type_photo_type"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    visit_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    photo_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# processing_jobs
# ─────────────────────────────────────────────────────────────────────────────

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    photo_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("visit_photos.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_costs: Mapped[Optional[dict]] = mapped_column(JSONB)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    photo: Mapped["VisitPhoto"] = relationship(back_populates="processing_jobs")
