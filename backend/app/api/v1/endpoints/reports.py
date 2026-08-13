from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import SiteVisit

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/{visit_id}/report", status_code=202)
async def generate_report(visit_id: str, db: AsyncSession = Depends(get_db)):
    visit = await db.get(SiteVisit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")
    try:
        from app.workers.tasks import generate_report_task
        task = generate_report_task.apply_async(args=[visit_id], queue="default")
        return {"job_id": task.id, "message": "Đang tạo báo cáo..."}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/{visit_id}/report/download")
async def download_report(visit_id: str, format: str = "pdf", db: AsyncSession = Depends(get_db)):
    import os
    visit = await db.get(SiteVisit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")
    path = f"/tmp/sitevisit/reports/{visit_id}/report.{format}"
    if not os.path.exists(path):
        raise HTTPException(404, "Báo cáo chưa được tạo. Gọi POST /report trước.")
    media = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(path=path, media_type=media, filename=f"site_visit_{visit_id[:8]}.{format}")
