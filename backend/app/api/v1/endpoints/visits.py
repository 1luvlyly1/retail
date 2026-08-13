"""
Site Visits — không có auth, ai cũng dùng được.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tavily import AsyncTavilyClient

from app.core.config import settings
from app.db.database import get_db
from app.models.models import Company, RequiredPhotoType, SiteVisit, VisitPhoto

_MST_RE = re.compile(r'\b(\d{10}(?:-\d{3})?)\b')

logger = structlog.get_logger(__name__)
router = APIRouter()


class VisitCreate(BaseModel):
    company_id: str
    created_by: Optional[str] = None   # tên người tạo, tuỳ điền
    visit_date: Optional[datetime] = None
    visit_type: str = "standard"
    notes: Optional[str] = None


class VisitUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    visit_date: Optional[datetime] = None


class VisitOut(BaseModel):
    id: str
    company_id: str
    created_by: Optional[str]
    visit_date: Optional[datetime]
    visit_type: str
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChecklistItem(BaseModel):
    photo_type: str
    description: Optional[str]
    is_mandatory: bool
    is_completed: bool
    photo_id: Optional[str] = None
    confidence_score: Optional[float] = None
    ai_description: Optional[str] = None
    ai_ocr_text: Optional[str] = None
    models_agreed: Optional[bool] = None


class ChecklistStatus(BaseModel):
    visit_id: str
    visit_type: str
    completed: List[str]
    missing: List[str]
    optional_missing: List[str]
    items: List[ChecklistItem]
    progress: str
    mandatory_progress: str
    all_mandatory_done: bool
    all_done: bool


@router.post("", response_model=VisitOut, status_code=201)
async def create_visit(
    payload: VisitCreate,
    db: AsyncSession = Depends(get_db),
):
    company = await db.get(Company, payload.company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    visit = SiteVisit(
        company_id=payload.company_id,
        created_by=payload.created_by,
        visit_date=payload.visit_date or datetime.utcnow(),
        visit_type=payload.visit_type,
        notes=payload.notes,
    )
    db.add(visit)
    await db.flush()
    logger.info("Visit created", visit_id=visit.id)
    return visit


@router.get("", response_model=List[VisitOut])
async def list_visits(
    status: Optional[str] = Query(None),
    visit_type: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    q = select(SiteVisit)
    if status:
        q = q.where(SiteVisit.status == status)
    if visit_type:
        q = q.where(SiteVisit.visit_type == visit_type)
    q = q.order_by(SiteVisit.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{visit_id}", response_model=VisitOut)
async def get_visit(visit_id: str, db: AsyncSession = Depends(get_db)):
    visit = await db.get(SiteVisit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")
    return visit


@router.patch("/{visit_id}", response_model=VisitOut)
async def update_visit(
    visit_id: str,
    payload: VisitUpdate,
    db: AsyncSession = Depends(get_db),
):
    visit = await db.get(SiteVisit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(visit, field, value)
    return visit


@router.get("/{visit_id}/checklist", response_model=ChecklistStatus)
async def get_checklist(visit_id: str, db: AsyncSession = Depends(get_db)):
    visit = await db.get(SiteVisit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")

    req_result = await db.execute(
        select(RequiredPhotoType)
        .where(RequiredPhotoType.visit_type == visit.visit_type)
        .order_by(RequiredPhotoType.order_index)
    )
    required_types = req_result.scalars().all()

    photos_result = await db.execute(
        select(VisitPhoto).where(
            VisitPhoto.visit_id == visit_id,
            VisitPhoto.processing_status == "done",
            VisitPhoto.photo_type.isnot(None),
        )
    )
    photo_map: dict = {}
    for photo in photos_result.scalars().all():
        if photo.photo_type:
            existing = photo_map.get(photo.photo_type)
            if not existing or (photo.confidence_score or 0) > (existing.confidence_score or 0):
                photo_map[photo.photo_type] = photo

    items, completed, missing, optional_missing = [], [], [], []
    for req in required_types:
        matched = photo_map.get(req.photo_type)
        is_done = matched is not None
        items.append(ChecklistItem(
            photo_type=req.photo_type,
            description=req.description,
            is_mandatory=req.is_mandatory,
            is_completed=is_done,
            photo_id=matched.id if matched else None,
            confidence_score=matched.confidence_score if matched else None,
            ai_description=matched.final_description if matched else None,
            ai_ocr_text=matched.ocr_text if matched else None,
            models_agreed=matched.models_agreed if matched else None,
        ))
        if is_done:
            completed.append(req.photo_type)
        elif req.is_mandatory:
            missing.append(req.photo_type)
        else:
            optional_missing.append(req.photo_type)

    total = len(required_types)
    mandatory_total = sum(1 for r in required_types if r.is_mandatory)
    mandatory_done = sum(1 for r in required_types if r.is_mandatory and r.photo_type in photo_map)

    return ChecklistStatus(
        visit_id=visit_id,
        visit_type=visit.visit_type,
        completed=completed,
        missing=missing,
        optional_missing=optional_missing,
        items=items,
        progress=f"{len(completed)}/{total}",
        mandatory_progress=f"{mandatory_done}/{mandatory_total}",
        all_mandatory_done=mandatory_done == mandatory_total,
        all_done=len(completed) == total,
    )


class TaxSearchResult(BaseModel):
    mst: Optional[str] = None
    results: List[dict] = []


@router.get("/{visit_id}/tax-search", response_model=TaxSearchResult)
async def tax_search(visit_id: str, db: AsyncSession = Depends(get_db)):
    """Tìm MST trong OCR ảnh rồi search Tavily, trả 5 link đầu."""
    res = await db.execute(
        select(VisitPhoto.ocr_text).where(
            VisitPhoto.visit_id == visit_id,
            VisitPhoto.ocr_text.isnot(None),
        )
    )
    mst = None
    for (text,) in res.all():
        m = _MST_RE.search(text or "")
        if m:
            mst = m.group(1)
            break

    if not mst:
        return TaxSearchResult()

    try:
        client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
        data = await client.search(f"mã số thuế {mst}", max_results=5)
        items = [
            {"url": r.get("url", ""), "snippet": (r.get("content") or "").strip()[:120]}
            for r in (data.get("results") or [])
        ]
        return TaxSearchResult(mst=mst, results=items)
    except Exception as exc:
        logger.warning("Tavily search failed", mst=mst, error=str(exc))
        return TaxSearchResult(mst=mst, results=[])
