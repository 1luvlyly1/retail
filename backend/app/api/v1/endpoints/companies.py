"""
Companies — lookup và get. Không có auth.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import Company

logger = structlog.get_logger(__name__)
router = APIRouter()


class TaxLookupRequest(BaseModel):
    tax_code: str
    visit_id: Optional[str] = None


class CompanyOut(BaseModel):
    id: str
    tax_code: str
    name: Optional[str]
    address: Optional[str]
    representative: Optional[str]
    industry: Optional[str]
    status: Optional[str]
    enrichment_status: str
    verified_at: Optional[datetime]
    created_at: datetime
    raw_data: Optional[dict] = None

    model_config = {"from_attributes": True}


@router.post("/lookup", response_model=CompanyOut, status_code=202)
async def lookup_company(
    payload: TaxLookupRequest,
    db: AsyncSession = Depends(get_db),
):
    tax_code = payload.tax_code.strip().replace("-", "").replace(".", "")

    result = await db.execute(select(Company).where(Company.tax_code == tax_code))
    company = result.scalar_one_or_none()

    if company and company.enrichment_status == "done":
        return company

    if not company:
        company = Company(tax_code=tax_code, enrichment_status="pending")
        db.add(company)
        await db.flush()

    try:
        from app.workers.tasks import enrich_company_task
        enrich_company_task.apply_async(
            args=[company.id, payload.visit_id],
            queue="enrichment",
        )
        company.enrichment_status = "running"
    except Exception as exc:
        logger.error("Enrichment dispatch failed", error=str(exc))
        company.enrichment_status = "failed"

    return company


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: str, db: AsyncSession = Depends(get_db)):
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    return company
