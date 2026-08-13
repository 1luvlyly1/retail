"""
Skill Files — upload, list, delete. Không có auth.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import SkillFile

logger = structlog.get_logger(__name__)
router = APIRouter()


class SkillFileOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    visit_type: Optional[list]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


def extract_text(file_path: Path, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            import fitz
            doc = fitz.open(str(file_path))
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
            return text.strip()
        except ImportError:
            return f"[PDF: {filename} — cần cài pymupdf]"
    elif suffix in (".docx", ".doc"):
        try:
            import docx
            doc = docx.Document(str(file_path))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            return f"[DOCX: {filename} — cần cài python-docx]"
    elif suffix == ".txt":
        return file_path.read_text(encoding="utf-8", errors="replace").strip()
    return f"[Không hỗ trợ: {suffix}]"


@router.post("", response_model=SkillFileOut, status_code=201)
async def upload_skill(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    visit_types: str = Form("standard"),
    db: AsyncSession = Depends(get_db),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".doc", ".txt"}:
        raise HTTPException(400, f"Không hỗ trợ '{suffix}'")

    content = await file.read()
    skills_dir = Path("/tmp/sitevisit/skills")
    skills_dir.mkdir(parents=True, exist_ok=True)
    saved_path = skills_dir / f"{uuid.uuid4()}{suffix}"
    saved_path.write_bytes(content)

    extracted = extract_text(saved_path, file.filename or "")
    visit_type_list = [v.strip() for v in visit_types.split(",") if v.strip()]

    skill = SkillFile(
        name=name,
        description=description,
        visit_type=visit_type_list,
        content=extracted[:50000],
        file_path=str(saved_path),
    )
    db.add(skill)
    await db.flush()
    return skill


@router.get("", response_model=List[SkillFileOut])
async def list_skills(
    visit_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(SkillFile).where(SkillFile.is_active == True)
    if visit_type:
        q = q.where(SkillFile.visit_type.contains([visit_type]))
    result = await db.execute(q)
    return result.scalars().all()


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, db: AsyncSession = Depends(get_db)):
    skill = await db.get(SkillFile, skill_id)
    if not skill:
        raise HTTPException(404, "Skill file not found")
    await db.delete(skill)


@router.patch("/{skill_id}/toggle", response_model=SkillFileOut)
async def toggle_skill(skill_id: str, db: AsyncSession = Depends(get_db)):
    skill = await db.get(SkillFile, skill_id)
    if not skill:
        raise HTTPException(404, "Skill file not found")
    skill.is_active = not skill.is_active
    return skill
