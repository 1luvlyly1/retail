"""
Context Builder — assembles system prompt + message history for Claude.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Company, Conversation, Message, SiteVisit, SkillFile, VisitPhoto

logger = structlog.get_logger(__name__)

BASE_SYSTEM_PROMPT = """Bạn là AI Assistant chuyên hỗ trợ nhân viên thực địa (site visit) tại công ty khách hàng.

Vai trò:
- Phân tích thông tin thu thập được từ thực địa
- Trả lời câu hỏi về công ty khách hàng dựa trên dữ liệu đã có
- Hỗ trợ lập báo cáo thực địa chuyên nghiệp
- Cảnh báo các điểm bất thường hoặc rủi ro

Nguyên tắc:
- Chỉ đưa ra thông tin dựa trên dữ liệu thực tế thu thập được
- Nếu thiếu thông tin, nói rõ và đề xuất cách thu thập thêm
- Ngôn ngữ chuyên nghiệp, súc tích
- Ưu tiên tiếng Việt trừ khi user dùng ngôn ngữ khác"""

MAX_CONTEXT_CHARS = 80_000
HISTORY_TURNS = 5


async def build_chat_context(
    db: AsyncSession,
    conversation_id: str,
    visit_id: str,
    user_message: str,
    image_urls: Optional[List[str]] = None,
) -> Tuple[str, List[dict]]:
    visit = await db.get(SiteVisit, visit_id)

    # Company info
    company_section = ""
    if visit and visit.company_id:
        company = await db.get(Company, visit.company_id)
        if company:
            company_section = _fmt_company(company)

    # Skill files
    skill_section = ""
    if visit:
        res = await db.execute(
            select(SkillFile).where(SkillFile.is_active == True)
        )
        skills = [
            s for s in res.scalars().all()
            if visit.visit_type in (s.visit_type or [])
        ]
        if skills:
            skill_section = _fmt_skills(skills)

    # Photo descriptions
    photo_section = ""
    res = await db.execute(
        select(VisitPhoto).where(
            VisitPhoto.visit_id == visit_id,
            VisitPhoto.processing_status == "done",
            VisitPhoto.final_description.isnot(None),
        ).order_by(VisitPhoto.created_at)
    )
    photos = res.scalars().all()
    if photos:
        photo_section = _fmt_photos(photos)

    # Assemble system prompt
    parts = [BASE_SYSTEM_PROMPT]
    if company_section:
        parts.append(company_section)
    if skill_section:
        parts.append(skill_section)
    if photo_section:
        parts.append(photo_section)

    system_prompt = "\n\n---\n\n".join(parts)
    if len(system_prompt) > MAX_CONTEXT_CHARS:
        system_prompt = system_prompt[:MAX_CONTEXT_CHARS] + "\n\n[... đã cắt bớt do quá dài]"

    # Message history (last N turns)
    res = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_TURNS * 2)
    )
    history = list(reversed(res.scalars().all()))
    messages = [{"role": m.role, "content": m.content} for m in history]

    # New user message
    if image_urls:
        content = [{"type": "text", "text": user_message}]
        for url in image_urls[:5]:
            content.append({"type": "image", "source": {"type": "url", "url": url}})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": user_message})

    return system_prompt, messages


def _fmt_company(company) -> str:
    status_label = {
        "hoat_dong": "✅ Hoạt động",
        "tam_dung": "⚠️ Tạm dừng",
        "giai_the": "❌ Giải thể",
    }.get(company.status or "", company.status or "Chưa xác định")

    return "\n".join([
        "## THÔNG TIN CÔNG TY KHÁCH HÀNG",
        f"- **MST**: {company.tax_code}",
        f"- **Tên**: {company.name or 'Chưa xác định'}",
        f"- **Địa chỉ**: {company.address or 'Chưa có'}",
        f"- **Người đại diện**: {company.representative or 'Chưa có'}",
        f"- **Ngành nghề**: {company.industry or 'Chưa có'}",
        f"- **Trạng thái**: {status_label}",
    ])


def _fmt_skills(skills: list) -> str:
    parts = ["## TÀI LIỆU HƯỚNG DẪN"]
    for s in skills:
        parts.append(f"### {s.name}")
        if s.description:
            parts.append(f"_{s.description}_")
        if s.content:
            parts.append(s.content[:10000])
    return "\n\n".join(parts)


def _fmt_photos(photos: list) -> str:
    parts = [f"## ẢNH ĐÃ CHỤP ({len(photos)} ảnh)"]
    for i, p in enumerate(photos, 1):
        parts.append(f"### Ảnh {i}: {p.original_filename} [{p.photo_type or 'chưa phân loại'}]")
        if p.final_description:
            parts.append(f"**Mô tả**: {p.final_description}")
        if p.ocr_text:
            parts.append(f"**OCR**: {p.ocr_text[:500]}{'...' if len(p.ocr_text) > 500 else ''}")
        if p.models_agreed is False:
            parts.append("⚠️ Hai AI không nhất quán về ảnh này")
    return "\n\n".join(parts)
