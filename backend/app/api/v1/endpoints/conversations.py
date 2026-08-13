"""
Conversations + SSE streaming. Không có auth.
Mỗi conversation là 1 tiến trình độc lập: tự tạo SiteVisit riêng.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import AsyncGenerator, List, Optional

import anthropic
import openai
import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.models.models import (
    Company, Conversation, Message,
    ProcessingJob, RequiredPhotoType, SiteVisit, VisitPhoto,
)
from app.services.context_builder import build_chat_context

logger = structlog.get_logger(__name__)
router = APIRouter()

ac = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
oc = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# USD per million tokens
_PRICE: dict[str, dict] = {
    "claude-sonnet-4-6":          {"input": 3.0,   "output": 15.0},
    "claude-sonnet-4-5":          {"input": 3.0,   "output": 15.0},
    "claude-opus-4-5":            {"input": 15.0,  "output": 75.0},
    "claude-opus-4-8":            {"input": 15.0,  "output": 75.0},
    "claude-haiku-4-5-20251001":  {"input": 0.8,   "output": 4.0},
    "gpt-4.1":                    {"input": 2.0,   "output": 8.0},
    "gpt-4.1-mini":               {"input": 0.4,   "output": 1.6},
    "gpt-4.1-nano":               {"input": 0.1,   "output": 0.4},
    "gpt-4o":                     {"input": 2.5,   "output": 10.0},
    "gpt-4o-mini":                {"input": 0.15,  "output": 0.6},
}

def _calc_cost(model: str, inp: int, out: int) -> float:
    p = _PRICE.get(model) or _PRICE.get("claude-sonnet-4-6")
    return (inp * p["input"] + out * p["output"]) / 1_000_000

VISIT_TYPE_LABELS = {
    "standard":  "Thẩm định tiêu chuẩn",
    "warehouse":  "Thẩm định kho",
    "factory":   "Thẩm định nhà máy",
}


# ── Schemas ──────────────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    title: Optional[str] = None
    visit_type: str = "standard"

class ConversationOut(BaseModel):
    id: str
    visit_id: str
    title: Optional[str]
    visit_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class MessageOut(BaseModel):
    id: int
    conversation_id: str
    role: str
    content: str
    metadata_: Optional[dict] = None
    created_at: datetime
    model_config = {"from_attributes": True}

class SendMessageRequest(BaseModel):
    content: str
    image_urls: Optional[List[str]] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_default_company(db: AsyncSession) -> Company:
    result = await db.execute(select(Company).limit(1))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(400, "Chưa có công ty nào trong hệ thống. Vui lòng tạo công ty trước.")
    return company


async def _gate_check(db: AsyncSession, visit_id: str):
    """Chặn chat nếu chưa có ảnh nào xác thực trong checklist."""
    visit = await db.get(SiteVisit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")

    req_result = await db.execute(
        select(RequiredPhotoType.photo_type)
        .where(RequiredPhotoType.visit_type == visit.visit_type)
    )
    required_types = {r for (r,) in req_result.all()}
    if not required_types:
        return

    done_result = await db.execute(
        select(VisitPhoto.photo_type).where(
            VisitPhoto.visit_id == visit_id,
            VisitPhoto.processing_status == "done",
            VisitPhoto.photo_type.isnot(None),
        )
    )
    done_types = {r for (r,) in done_result.all()}

    if not (done_types & required_types):
        raise HTTPException(
            400,
            "Cần có ít nhất 1 ảnh xác thực trong checklist trước khi đặt câu hỏi. "
            "Vui lòng upload ảnh và chờ AI phân tích.",
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Tạo conversation mới, đồng thời tạo SiteVisit độc lập cho nó."""
    company = await _get_default_company(db)

    visit = SiteVisit(
        company_id=company.id,
        visit_type=payload.visit_type,
        visit_date=datetime.utcnow(),
        status="in_progress",
    )
    db.add(visit)
    await db.flush()

    now_vn = datetime.now().strftime("%d/%m/%Y %H:%M")
    raw_title = payload.title.strip() if payload.title and payload.title.strip() else ""
    visit_label = VISIT_TYPE_LABELS.get(payload.visit_type, payload.visit_type)
    title = f"{raw_title} — {now_vn}" if raw_title else f"{visit_label} — {now_vn}"

    conv = Conversation(visit_id=visit.id, title=title)
    db.add(conv)
    await db.flush()

    # Gắn visit_type vào output qua attribute tạm
    result = ConversationOut.model_validate(conv)
    result.visit_type = payload.visit_type
    return result


@router.get("", response_model=List[ConversationOut])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    """List tất cả conversations mới nhất (không filter theo visit)."""
    result = await db.execute(
        select(Conversation).order_by(Conversation.updated_at.desc()).limit(50)
    )
    convs = result.scalars().all()
    out = []
    for c in convs:
        visit = await db.get(SiteVisit, c.visit_id)
        item = ConversationOut.model_validate(c)
        item.visit_type = visit.visit_type if visit else None
        out.append(item)
    return out


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    visit = await db.get(SiteVisit, conv.visit_id)
    result = ConversationOut.model_validate(conv)
    result.visit_type = visit.visit_type if visit else None
    return result


@router.get("/{conversation_id}/messages", response_model=List[MessageOut])
async def list_messages(conversation_id: str, db: AsyncSession = Depends(get_db)):
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


@router.get("/{conversation_id}/cost")
async def get_cost(conversation_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Message.metadata_).where(
            Message.conversation_id == conversation_id,
            Message.role == "assistant",
        )
    )
    # model_name -> {input_tok, output_tok, cost_usd}
    models: dict[str, dict] = {}

    def _add(model: str, tok: dict):
        inp, out = tok.get("input", 0), tok.get("output", 0)
        cost = _calc_cost(model, inp, out)
        if model not in models:
            models[model] = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        models[model]["input_tokens"]  += inp
        models[model]["output_tokens"] += out
        models[model]["cost_usd"]      += cost

    for (meta,) in res.all():
        if not meta:
            continue
        _add(meta.get("sonnet_model", settings.CLAUDE_SONNET_MODEL), meta.get("sonnet_tokens") or {})
        if meta.get("gpt4_tokens"):
            _add(meta.get("gpt4_model", settings.GPT4_MODEL), meta.get("gpt4_tokens") or {})

    total = sum(v["cost_usd"] for v in models.values())
    breakdown = [
        {"model": m, **{k: round(v, 6) if k == "cost_usd" else v for k, v in d.items()}}
        for m, d in models.items()
    ]
    # Photo processing costs từ ProcessingJob.token_costs
    photo_res = await db.execute(
        select(ProcessingJob.token_costs)
        .join(VisitPhoto, ProcessingJob.photo_id == VisitPhoto.id)
        .where(
            VisitPhoto.visit_id == (
                select(Conversation.visit_id)
                .where(Conversation.id == conversation_id)
                .scalar_subquery()
            ),
            ProcessingJob.token_costs.isnot(None),
        )
    )
    for (token_costs,) in photo_res.all():
        for model, tok in (token_costs or {}).items():
            _add(model, tok)

    total = sum(v["cost_usd"] for v in models.values())
    breakdown = [
        {"model": m, **{k: round(v, 6) if k == "cost_usd" else v for k, v in d.items()}}
        for m, d in models.items()
    ]
    breakdown.sort(key=lambda x: x["cost_usd"], reverse=True)
    return {"total_usd": round(total, 6), "breakdown": breakdown}


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    await _gate_check(db, conv.visit_id)

    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=payload.content,
        image_urls=payload.image_urls,
    )
    db.add(user_msg)
    await db.commit()

    system_prompt, messages = await build_chat_context(
        db=db,
        conversation_id=conversation_id,
        visit_id=conv.visit_id,
        user_message=payload.content,
        image_urls=payload.image_urls,
    )

    from app.db.database import AsyncSessionLocal

    queue: asyncio.Queue = asyncio.Queue()

    async def _background():
        """Chạy độc lập — không bị cancel khi client disconnect."""
        sonnet_response = ""
        gpt4_response   = ""
        sonnet_tokens: dict = {}
        gpt4_tokens: dict   = {}
        start = time.time()

        async def _call_gpt4() -> str:
            nonlocal gpt4_tokens
            try:
                resp = await oc.chat.completions.create(
                    model=settings.GPT4_MODEL,
                    max_tokens=settings.CLAUDE_MAX_TOKENS,
                    messages=[{"role": "system", "content": system_prompt}] + messages,
                )
                if resp.usage:
                    gpt4_tokens = {"input": resp.usage.prompt_tokens, "output": resp.usage.completion_tokens}
                return resp.choices[0].message.content or ""
            except Exception as exc:
                logger.error("GPT4 chat error", error=str(exc))
                return f"[GPT-4 lỗi: {exc}]"

        gpt4_task = asyncio.create_task(_call_gpt4())

        try:
            async with ac.messages.stream(
                model=settings.CLAUDE_SONNET_MODEL,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    sonnet_response += text
                    await queue.put({"type": "sonnet_token", "content": text})
                final = await stream.get_final_message()
                sonnet_tokens = {"input": final.usage.input_tokens, "output": final.usage.output_tokens}
        except Exception as exc:
            logger.error("Sonnet stream error", error=str(exc))
            await queue.put({"type": "error", "message": str(exc)})
            gpt4_task.cancel()
            await queue.put(None)
            return

        gpt4_response = await gpt4_task
        latency_ms = int((time.time() - start) * 1000)

        # Save trước khi yield — đảm bảo không mất data dù client đã disconnect
        try:
            async with AsyncSessionLocal() as save_db:
                save_db.add(Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=sonnet_response,
                    metadata_={
                        "gpt4": gpt4_response,
                        "sonnet_model": settings.CLAUDE_SONNET_MODEL,
                        "gpt4_model": settings.GPT4_MODEL,
                        "sonnet_tokens": sonnet_tokens,
                        "gpt4_tokens": gpt4_tokens,
                        "latency_ms": latency_ms,
                    },
                ))
                conv_upd = await save_db.get(Conversation, conversation_id)
                if conv_upd:
                    conv_upd.updated_at = datetime.utcnow()
                await save_db.commit()
        except Exception as exc:
            logger.error("Save message failed", error=str(exc))

        await queue.put({"type": "gpt4_done", "content": gpt4_response})
        await queue.put({"type": "done", "latency_ms": latency_ms})
        await queue.put(None)  # sentinel

    bg_task = asyncio.create_task(_background())

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            # Client disconnect — background task tiếp tục save
            if not bg_task.done():
                await asyncio.shield(bg_task)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
