"""
Photos — upload, list, detail. Không có auth.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.models.models import ProcessingJob, SiteVisit, VisitPhoto

logger = structlog.get_logger(__name__)
router = APIRouter()

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/heic", "image/heif", "image/webp"}


class PhotoOut(BaseModel):
    id: str
    visit_id: str
    original_filename: str
    file_size_bytes: Optional[int]
    photo_type: Optional[str]
    processing_status: str
    gdrive_url: Optional[str]
    final_description: Optional[str]
    ocr_text: Optional[str]
    models_agreed: Optional[bool]
    confidence_score: Optional[float]
    created_at: datetime
    processing_time_s: Optional[float] = None

    model_config = {"from_attributes": True}


class PhotoDetail(PhotoOut):
    sonnet_description: Optional[str]
    gpt4_description: Optional[str]
    opus_description: Optional[str]
    ocr_layout: Optional[dict]
    comparison_notes: Optional[str]


@router.post("/visits/{visit_id}/photos", response_model=List[PhotoOut], status_code=201)
async def upload_photos(
    visit_id: str,
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    visit = await db.get(SiteVisit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")
    if visit.status == "completed":
        raise HTTPException(400, "Cannot upload to a completed visit")
    if len(files) > 10:
        raise HTTPException(400, "Max 10 photos per upload")

    created = []

    for file in files:
        content_type = file.content_type or ""
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(400, f"Unsupported type '{content_type}' for '{file.filename}'")

        content = await file.read()
        if len(content) > settings.MAX_FILE_SIZE_BYTES:
            raise HTTPException(400, f"'{file.filename}' exceeds {settings.MAX_FILE_SIZE_MB}MB")

        tmp_path = settings.TMP_DIR / f"{uuid.uuid4()}_{file.filename}"
        tmp_path.write_bytes(content)

        photo = VisitPhoto(
            visit_id=visit_id,
            original_filename=file.filename or "unknown.jpg",
            file_size_bytes=len(content),
            mime_type=content_type,
            processing_status="pending",
        )
        db.add(photo)
        await db.flush()

        job = ProcessingJob(photo_id=photo.id, status="queued")
        db.add(job)
        await db.flush()

        try:
            from app.workers.tasks import process_photo_task
            task = process_photo_task.apply_async(
                args=[photo.id, str(tmp_path), visit_id],
                queue=settings.PHOTO_PROCESSING_QUEUE,
            )
            job.celery_task_id = task.id
        except Exception as exc:
            logger.error("Celery dispatch failed", error=str(exc))
            photo.processing_status = "failed"
            job.status = "failed"
            job.error_message = str(exc)

        created.append(photo)

    return created


@router.get("/visits/{visit_id}/photos", response_model=List[PhotoOut])
async def list_photos(visit_id: str, db: AsyncSession = Depends(get_db)):
    visit = await db.get(SiteVisit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")
    photos_result = await db.execute(
        select(VisitPhoto)
        .where(VisitPhoto.visit_id == visit_id)
        .order_by(VisitPhoto.created_at.desc())
    )
    photos = photos_result.scalars().all()

    # Lấy thời gian xử lý từ ProcessingJob (started_at → completed_at)
    photo_ids = [p.id for p in photos]
    jobs_result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.photo_id.in_(photo_ids))
        .order_by(ProcessingJob.created_at.desc())
    )
    # Chỉ lấy job mới nhất mỗi photo
    job_map: Dict[str, ProcessingJob] = {}
    for job in jobs_result.scalars().all():
        if job.photo_id not in job_map:
            job_map[job.photo_id] = job

    out = []
    for photo in photos:
        item = PhotoOut.model_validate(photo)
        job = job_map.get(photo.id)
        if job and job.started_at and job.completed_at:
            delta = job.completed_at - job.started_at
            item.processing_time_s = round(delta.total_seconds(), 1)
        out.append(item)
    return out


@router.get("/photos/{photo_id}", response_model=PhotoDetail)
async def get_photo(photo_id: str, db: AsyncSession = Depends(get_db)):
    photo = await db.get(VisitPhoto, photo_id)
    if not photo:
        raise HTTPException(404, "Photo not found")
    return photo
