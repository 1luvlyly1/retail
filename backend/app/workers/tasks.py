"""
Celery Tasks — photo processing, company enrichment, report generation.
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog
from celery import Task

from app.core.config import settings
from app.workers.celery_app import celery_app

# Cấu hình structlog cho Celery worker process (độc lập với FastAPI process)
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger(__name__)


def run_async(coro):
    """Chạy coroutine trong event loop của worker process hiện tại.

    Tái dụng loop (đã tạo bởi worker_process_init) thay vì tạo mới + đóng
    mỗi task → tránh 'attached to a different loop' khi engine pool bị fork.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1: Process Photo
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_photo_task",
    max_retries=settings.CELERY_MAX_RETRIES,
    default_retry_delay=30,
    queue="photo_processing",
)
def process_photo_task(self: Task, photo_id: str, tmp_path: str, visit_id: str):
    logger.info("Processing photo", photo_id=photo_id)
    try:
        return run_async(_process_photo(photo_id, tmp_path, visit_id))
    except Exception as exc:
        logger.error("Photo failed", photo_id=photo_id, error=str(exc))
        run_async(_mark_photo_failed(photo_id, str(exc)))
        raise self.retry(exc=exc) from exc


async def _process_photo(photo_id: str, tmp_path: str, visit_id: str):
    from app.db.database import get_db_context
    from app.models.models import ProcessingJob, SiteVisit, VisitPhoto
    from app.services.local_storage import save_photo_locally
    from app.services.image_processor import extract_exif_datetime, resize_image_if_needed
    from app.services.event_bus import publish_visit_event
    from sqlalchemy import select

    # Mark as processing
    async with get_db_context() as db:
        photo = await db.get(VisitPhoto, photo_id)
        if not photo:
            raise ValueError(f"Photo {photo_id} not found")
        photo.processing_status = "processing"

        res = await db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.photo_id == photo_id)
            .order_by(ProcessingJob.created_at.desc())
        )
        job = res.scalar_one_or_none()
        if job:
            job.status = "running"
            job.started_at = datetime.utcnow()

        mime_type = photo.mime_type or "image/jpeg"
        await db.commit()

    # Step 1: Resize
    file_path = Path(tmp_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Temp file missing: {tmp_path}")

    resized_path, _ = resize_image_if_needed(file_path, settings.PROCESSED_MAX_SIZE_BYTES)
    captured_at = extract_exif_datetime(file_path)

    # Step 2: Lưu ảnh vĩnh viễn trên Mac Mini
    async with get_db_context() as db:
        visit = await db.get(SiteVisit, visit_id)
        company_id = visit.company_id if visit else "unknown"
        visit_date = (visit.visit_date or datetime.utcnow()).strftime("%Y-%m-%d") if visit else "unknown"

    storage_result = await save_photo_locally(
        file_path=resized_path,
        filename=file_path.name,
        company_id=company_id,
        visit_date=visit_date,
    )

    # Step 3: Parallel AI
    t0 = time.monotonic()
    image_b64 = base64.standard_b64encode(resized_path.read_bytes()).decode()
    sonnet_desc, gpt4_desc, describe_tokens = await _parallel_describe(image_b64, mime_type)
    t_ai = time.monotonic() - t0
    logger.info("AI describe done", photo_id=photo_id, elapsed_s=round(t_ai, 1))

    # Trích phan_loai từ cả hai để so sánh trực tiếp
    sonnet_type = _parse_ai_response(sonnet_desc)[0]
    gpt4_type   = _parse_ai_response(gpt4_desc)[0]

    # Step 4: Compare — nếu phan_loai khác nhau, mặc định disagreed không cần gọi judge về nội dung
    t1 = time.monotonic()
    compare_tokens: dict = {}
    if sonnet_type != gpt4_type:
        _, confidence, text_notes, compare_tokens = await _compare(sonnet_desc, gpt4_desc)
        agreed = False
        notes  = f"phan_loai khác nhau (Sonnet={sonnet_type}, GPT4={gpt4_type}). {text_notes}".strip()
        logger.warning("phan_loai mismatch → Opus required",
                       photo_id=photo_id, sonnet=sonnet_type, gpt4=gpt4_type)
    else:
        agreed, confidence, notes, compare_tokens = await _compare(sonnet_desc, gpt4_desc)
    t_compare = time.monotonic() - t1
    logger.info("Compare done", photo_id=photo_id, agreed=agreed,
                confidence=round(confidence, 2), elapsed_s=round(t_compare, 1))

    # Step 5: Opus fallback
    opus_desc = None
    opus_tokens: dict = {}
    final_desc = sonnet_desc
    if not agreed:
        t2 = time.monotonic()
        opus_desc, opus_tokens = await _opus_verify(image_b64, mime_type, sonnet_desc, gpt4_desc)
        final_desc = opus_desc
        logger.info("Opus done", photo_id=photo_id, elapsed_s=round(time.monotonic() - t2, 1))

    # Step 6: Extract metadata (photo_type, ocr_text, ocr_layout, mô tả sạch)
    photo_type, ocr_text, ocr_layout, clean_description = _parse_ai_response(final_desc)

    # Step 7: Save
    async with get_db_context() as db:
        photo = await db.get(VisitPhoto, photo_id)
        if photo:
            photo.processing_status = "done"
            photo.gdrive_file_id = storage_result.get("file_id")     # relative path local
            photo.gdrive_url = storage_result.get("web_view_url")    # /media/... URL
            photo.gdrive_folder = storage_result.get("folder_path")
            photo.captured_at = captured_at
            photo.sonnet_description = sonnet_desc
            photo.gpt4_description = gpt4_desc
            photo.opus_description = opus_desc
            photo.final_description = clean_description or final_desc  # mô tả sạch, không có ```json
            photo.photo_type = photo_type
            photo.ocr_text = ocr_text
            photo.ocr_layout = ocr_layout
            photo.models_agreed = agreed
            photo.confidence_score = confidence
            photo.comparison_notes = notes

        res = await db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.photo_id == photo_id)
            .order_by(ProcessingJob.created_at.desc())
        )
        job = res.scalar_one_or_none()
        if job:
            job.status = "done"
            job.completed_at = datetime.utcnow()
            # Merge tất cả token counts: describe + compare + opus (nếu có)
            all_tokens: dict[str, dict] = {}
            for src in (describe_tokens, compare_tokens, opus_tokens):
                for model, tok in src.items():
                    if model not in all_tokens:
                        all_tokens[model] = {"input": 0, "output": 0}
                    all_tokens[model]["input"]  += tok.get("input", 0)
                    all_tokens[model]["output"] += tok.get("output", 0)
            job.token_costs = all_tokens
        await db.commit()

    # Step 8: Publish event qua Redis -> FastAPI process forward tới WebSocket thật
    await publish_visit_event(visit_id, {
        "type": "photo_processed",
        "photo_id": photo_id,
        "photo_type": photo_type,
        "models_agreed": agreed,
        "confidence": confidence,
        "status": "done",
    })

    # Step 9: Checklist update
    await _emit_checklist(visit_id)

    # Cleanup
    try:
        file_path.unlink(missing_ok=True)
        if resized_path != file_path:
            resized_path.unlink(missing_ok=True)
    except Exception:
        pass

    total_s = round(time.monotonic() - t0, 1)
    logger.info("Photo done", photo_id=photo_id, photo_type=photo_type,
                agreed=agreed, total_s=total_s)
    return {"photo_id": photo_id, "photo_type": photo_type, "agreed": agreed}


DESCRIBE_PROMPT = """Phân tích ảnh này và trả lời CHÍNH XÁC theo format JSON dưới đây (không có text nào khác):

{
  "mo_ta": "mô tả ngắn gọn nội dung ảnh trong 2-3 câu",
  "phan_loai": "chọn MỘT trong: biển_hiệu | mặt_tiền | khu_vực_làm_việc | dây_chuyền_sản_xuất | kho_nguyên_liệu | kho_thành_phẩm | kho | giấy_phép_kinh_doanh | nội_thất | khác",
  "ocr_text": "chỉ thông tin ĐỊNH DANH quan trọng (tên công ty, số đăng ký, ngày cấp, cơ quan cấp), tối đa 500 ký tự, để trống nếu không có chữ",
  "bat_thuong": "điểm bất thường cần chú ý nếu có, hoặc để trống"
}"""


async def _parallel_describe(image_b64: str, mime_type: str) -> tuple[str, str, dict]:
    """Returns (sonnet_text, gpt4_text, token_counts)."""
    import anthropic
    import openai

    ac = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    oc = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def sonnet():
        msg = await ac.messages.create(
            model=settings.CLAUDE_SONNET_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
                {"type": "text", "text": DESCRIBE_PROMPT},
            ]}],
        )
        return msg.content[0].text, {"input": msg.usage.input_tokens, "output": msg.usage.output_tokens}

    async def gpt4():
        resp = await oc.chat.completions.create(
            model=settings.GPT4_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                {"type": "text", "text": DESCRIBE_PROMPT},
            ]}],
        )
        usage = resp.usage
        tok = {"input": usage.prompt_tokens, "output": usage.completion_tokens} if usage else {}
        return resp.choices[0].message.content, tok

    results = await asyncio.gather(sonnet(), gpt4(), return_exceptions=True)
    s_text = results[0][0] if not isinstance(results[0], Exception) else f'{{"error": "{results[0]}"}}'
    s_tok  = results[0][1] if not isinstance(results[0], Exception) else {}
    g_text = results[1][0] if not isinstance(results[1], Exception) else f'{{"error": "{results[1]}"}}'
    g_tok  = results[1][1] if not isinstance(results[1], Exception) else {}
    return s_text, g_text, {
        settings.CLAUDE_SONNET_MODEL: s_tok,
        settings.GPT4_MODEL: g_tok,
    }


async def _compare(sonnet: str, gpt4: str) -> tuple[bool, float, str, dict]:
    """Returns (agreed, confidence, notes, token_counts)."""
    import anthropic

    ac = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = f"""So sánh 2 mô tả ảnh sau về mức độ nhất quán.

Mô tả 1: {sonnet[:1000]}
Mô tả 2: {gpt4[:1000]}

Trả về JSON:
{{"nhat_quan": true/false, "do_tin_cay": 0.0-1.0, "ly_do": "..."}}"""

    try:
        msg = await ac.messages.create(
            model=settings.CLAUDE_SONNET_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        tok = {"input": msg.usage.input_tokens, "output": msg.usage.output_tokens}
        m = re.search(r'\{.*\}', msg.content[0].text, re.DOTALL)
        if m:
            data = json.loads(m.group())
            return data.get("nhat_quan", True), data.get("do_tin_cay", 0.75), data.get("ly_do", ""), {settings.CLAUDE_SONNET_MODEL: tok}
    except Exception as exc:
        logger.warning("Compare failed", error=str(exc))
    return True, 0.7, "", {}


async def _opus_verify(image_b64: str, mime_type: str, s: str, g: str) -> tuple[str, dict]:
    import anthropic

    ac = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = f"""Hai AI mô tả ảnh này khác nhau. Hãy phân tích và đưa ra mô tả chính xác nhất.
Mô tả 1: {s[:600]}
Mô tả 2: {g[:600]}
{DESCRIBE_PROMPT}"""

    msg = await ac.messages.create(
        model=settings.CLAUDE_OPUS_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
            {"type": "text", "text": prompt},
        ]}],
    )
    tok = {"input": msg.usage.input_tokens, "output": msg.usage.output_tokens}
    return msg.content[0].text, {settings.CLAUDE_OPUS_MODEL: tok}


# GPT4 đôi khi trả phan_loai dạng ASCII không dấu — map về chuẩn
_PHAN_LOAI_ALIASES: dict[str, str] = {
    "khu_vuc_lam_viec":        "khu_vực_làm_việc",
    "bien_hieu":               "biển_hiệu",
    "mat_tien":                "mặt_tiền",
    "giay_phep_kinh_doanh":    "giấy_phép_kinh_doanh",
    "day_chuyen_san_xuat":     "dây_chuyền_sản_xuất",
    "kho_nguyen_lieu":         "kho_nguyên_liệu",
    "kho_thanh_pham":          "kho_thành_phẩm",
    "noi_that":                "nội_thất",
}


def _normalize_phan_loai(value: str) -> str:
    v = value.strip()
    # Nếu AI trả nhiều loại ngăn cách bởi | hoặc ,  → lấy loại đầu tiên
    for sep in ("|", ",", "/"):
        if sep in v:
            v = v.split(sep)[0].strip()
            break
    return _PHAN_LOAI_ALIASES.get(v, v)


def _parse_ai_response(text: str) -> tuple[Optional[str], Optional[str], Optional[dict], Optional[str]]:
    """
    Parse JSON response từ AI (có thể bọc trong ```json ... ```).
    Trả về (photo_type, ocr_text, ocr_layout, clean_description_for_humans).
    """
    # Thử parse JSON đầy đủ
    try:
        cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.MULTILINE)
        m = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if m:
            data = json.loads(m.group())
            ocr = data.get("ocr_text", "")
            mo_ta = data.get("mo_ta", "")
            bat_thuong = data.get("bat_thuong", "")
            clean_parts = [mo_ta] if mo_ta else []
            if bat_thuong:
                clean_parts.append(f"⚠️ Điểm bất thường: {bat_thuong}")
            clean_description = "\n\n".join(clean_parts) or None
            return (
                _normalize_phan_loai(data.get("phan_loai", "khác")),
                ocr,
                {"raw_text": ocr} if ocr else None,
                clean_description,
            )
    except Exception:
        pass

    # Fallback: JSON bị cắt ngắn hoặc không hợp lệ → dùng regex trích trực tiếp
    try:
        m_type = re.search(r'"phan_loai"\s*:\s*"([^"]+)"', text)
        m_ocr = re.search(r'"ocr_text"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        m_mota = re.search(r'"mo_ta"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m_type:
            photo_type = _normalize_phan_loai(m_type.group(1))
            ocr = m_ocr.group(1).replace('\\n', '\n').strip() if m_ocr else None
            mo_ta = m_mota.group(1).strip() if m_mota else None
            return photo_type, ocr, {"raw_text": ocr} if ocr else None, mo_ta
    except Exception:
        pass

    return "khác", None, None, None


async def _emit_checklist(visit_id: str):
    from app.services.event_bus import publish_visit_event
    from app.db.database import get_db_context
    from app.models.models import RequiredPhotoType, SiteVisit, VisitPhoto
    from sqlalchemy import select

    async with get_db_context() as db:
        visit = await db.get(SiteVisit, visit_id)
        if not visit:
            return

        res = await db.execute(
            select(RequiredPhotoType).where(RequiredPhotoType.visit_type == visit.visit_type)
        )
        required = res.scalars().all()

        res = await db.execute(
            select(VisitPhoto).where(
                VisitPhoto.visit_id == visit_id,
                VisitPhoto.processing_status == "done",
                VisitPhoto.photo_type.isnot(None),
            )
        )
        done_types = {p.photo_type for p in res.scalars().all()}

        completed = [r.photo_type for r in required if r.photo_type in done_types]
        missing = [r.photo_type for r in required if r.photo_type not in done_types and r.is_mandatory]

        await publish_visit_event(visit_id, {
            "type": "checklist_update",
            "visit_id": visit_id,
            "completed": completed,
            "missing": missing,
            "progress": f"{len(completed)}/{len(required)}",
            "all_done": len(missing) == 0,
        })


async def _mark_photo_failed(photo_id: str, error: str):
    from app.db.database import get_db_context
    from app.models.models import ProcessingJob, VisitPhoto
    from sqlalchemy import select

    async with get_db_context() as db:
        photo = await db.get(VisitPhoto, photo_id)
        if photo:
            photo.processing_status = "failed"
        res = await db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.photo_id == photo_id)
            .order_by(ProcessingJob.created_at.desc())
        )
        job = res.scalar_one_or_none()
        if job:
            job.status = "failed"
            job.error_message = error
            job.completed_at = datetime.utcnow()
        await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2: Company Enrichment
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.enrich_company_task",
    max_retries=2,
    default_retry_delay=60,
    queue="enrichment",
)
def enrich_company_task(self: Task, company_id: str, visit_id: Optional[str] = None):
    logger.info("Enriching company", company_id=company_id)
    try:
        return run_async(_enrich_company(company_id, visit_id))
    except Exception as exc:
        logger.error("Enrichment failed", company_id=company_id, error=str(exc))
        run_async(_mark_company_failed(company_id, str(exc)))
        raise self.retry(exc=exc) from exc


async def _enrich_company(company_id: str, visit_id: Optional[str]):
    from app.db.database import get_db_context
    from app.models.models import Company
    from app.services.enrichment_agent import run_enrichment_agent

    async with get_db_context() as db:
        company = await db.get(Company, company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")
        tax_code = company.tax_code

    result = await run_enrichment_agent(tax_code=tax_code, visit_id=visit_id)

    async with get_db_context() as db:
        company = await db.get(Company, company_id)
        if company:
            company.name = result.get("name") or company.name
            company.address = result.get("address") or company.address
            company.representative = result.get("representative") or company.representative
            company.industry = result.get("industry") or company.industry
            company.status = result.get("status") or company.status
            company.raw_data = result
            company.enrichment_status = "done"
            company.verified_at = datetime.utcnow()
        await db.commit()

    if visit_id:
        from app.services.event_bus import publish_visit_event
        await publish_visit_event(visit_id, {
            "type": "company_enriched",
            "company_id": company_id,
            "name": result.get("name"),
            "status": result.get("status"),
            "name_mismatch": result.get("name_mismatch", False),
        })

    return result


async def _mark_company_failed(company_id: str, error: str):
    from app.db.database import get_db_context
    from app.models.models import Company

    async with get_db_context() as db:
        company = await db.get(Company, company_id)
        if company:
            company.enrichment_status = "failed"
            company.raw_data = {"error": error}
        await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3: Report Generation
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.generate_report_task",
    max_retries=1,
    queue="default",
)
def generate_report_task(self: Task, visit_id: str):
    logger.info("Generating report", visit_id=visit_id)
    try:
        return run_async(_generate_report(visit_id))
    except Exception as exc:
        raise self.retry(exc=exc) from exc


async def _generate_report(visit_id: str):
    # Phase 5 — placeholder
    report_dir = Path(f"/tmp/sitevisit/reports/{visit_id}")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.pdf").write_text(f"Report for {visit_id}")
    return {"visit_id": visit_id, "path": str(report_dir / "report.pdf")}
