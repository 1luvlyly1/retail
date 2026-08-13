from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, Optional

import structlog
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic
from tavily import TavilyClient

from app.core.config import settings

logger = structlog.get_logger(__name__)


@tool
def search_tax_portal(tax_code: str) -> str:
    """Tra cứu công ty từ cổng thuế Việt Nam. Input: mã số thuế."""
    import httpx
    try:
        resp = httpx.get(
            f"https://api.tracuunnt.com/api/taxpayer/{tax_code}",
            headers={"User-Agent": "SiteVisitBot/1.0"},
            timeout=15,
        )
        if resp.status_code == 200:
            d = resp.json().get("data", {})
            if d:
                return (
                    f"Tên: {d.get('ten', 'N/A')}\n"
                    f"Địa chỉ: {d.get('diachi', 'N/A')}\n"
                    f"Người đại diện: {d.get('nguoiDaiDien', 'N/A')}\n"
                    f"Trạng thái: {d.get('trangThai', 'N/A')}\n"
                    f"Ngành nghề: {d.get('nganhNghe', 'N/A')}"
                )
    except Exception as exc:
        logger.warning("Tax portal failed", error=str(exc))

    # Fallback: Tavily
    try:
        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        res = client.search(query=f"mã số thuế {tax_code} thông tin công ty", max_results=3)
        texts = [r.get("content", "")[:400] for r in res.get("results", [])[:3]]
        return "Kết quả tìm kiếm:\n" + "\n---\n".join(texts)
    except Exception as exc:
        return f"Không tìm thấy: {exc}"


@tool
def tavily_web_search(query: str) -> str:
    """Tìm kiếm thông tin công ty trên web. Input: câu truy vấn."""
    try:
        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        res = client.search(query=query, max_results=5)
        parts = [
            f"Nguồn: {r.get('url', '')}\n{r.get('content', '')[:400]}"
            for r in res.get("results", [])[:5]
        ]
        return "\n\n".join(parts) or "Không có kết quả"
    except Exception as exc:
        return f"Lỗi: {exc}"


@tool
def cross_check_name(names: str) -> str:
    """
    So sánh tên trên biển hiệu với tên đăng ký thuế.
    Input format: "tên_biển_hiệu|tên_thuế"
    """
    parts = names.split("|", 1)
    if len(parts) != 2:
        return "Format sai. Dùng: tên_biển_hiệu|tên_thuế"

    sign_name, tax_name = parts[0].strip(), parts[1].strip()

    def norm(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r'[^\w\s]', ' ', s)
        s = re.sub(r'\s+', ' ', s)
        for suffix in ['công ty tnhh', 'công ty cp', 'cty tnhh', 'co., ltd', 'ltd']:
            s = s.replace(suffix, '').strip()
        return s

    n1, n2 = norm(sign_name), norm(tax_name)
    if n1 == n2:
        return "✅ Tên khớp hoàn toàn"
    if n1 in n2 or n2 in n1:
        return f"⚠️ Tên tương tự nhưng không hoàn toàn khớp:\n- Biển hiệu: {sign_name}\n- Thuế: {tax_name}"
    return (
        f"🚨 CẢNH BÁO: Tên KHÔNG khớp!\n"
        f"- Biển hiệu: {sign_name}\n"
        f"- Đăng ký thuế: {tax_name}"
    )


AGENT_PROMPT = PromptTemplate.from_template("""Bạn là agent tra cứu thông tin công ty.

Nhiệm vụ: Thu thập thông tin công ty có MST: {tax_code}
{ocr_hint}

Tools: {tools}
Tool names: {tool_names}

Quy trình:
1. Gọi search_tax_portal với MST
2. Nếu cần thêm, gọi tavily_web_search
3. Nếu có tên từ OCR, gọi cross_check_name với format "tên_ocr|tên_thuế"
4. Tổng hợp JSON cuối cùng

Format:
Thought: ...
Action: tên_tool
Action Input: input
Observation: kết quả
... (lặp)
Thought: Đủ thông tin rồi
Final Answer: {{"name": "...", "address": "...", "representative": "...", "industry": "...", "status": "hoat_dong|tam_dung|giai_the", "name_mismatch": false, "mismatch_detail": ""}}

{agent_scratchpad}

Question: Tra cứu MST {tax_code}
""")


async def run_enrichment_agent(tax_code: str, visit_id: Optional[str] = None) -> Dict[str, Any]:
    ocr_hint = await _get_ocr_hint(visit_id) if visit_id else ""

    llm = ChatAnthropic(
        model=settings.CLAUDE_SONNET_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=2048,
        temperature=0,
    )
    tools = [search_tax_portal, tavily_web_search, cross_check_name]
    agent = create_react_agent(llm, tools, AGENT_PROMPT)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=8,
        verbose=False,
        handle_parsing_errors=True,
    )

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: executor.invoke({"tax_code": tax_code, "ocr_hint": ocr_hint}),
        )
        output = result.get("output", "")
        m = re.search(r'\{.*\}', output, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as exc:
        logger.error("Agent failed", tax_code=tax_code, error=str(exc))

    return {"name": None, "address": None, "representative": None,
            "industry": None, "status": None, "name_mismatch": False}


async def _get_ocr_hint(visit_id: str) -> str:
    try:
        from app.db.database import get_db_context
        from app.models.models import VisitPhoto
        from sqlalchemy import select
        async with get_db_context() as db:
            res = await db.execute(
                select(VisitPhoto).where(
                    VisitPhoto.visit_id == visit_id,
                    VisitPhoto.photo_type == "biển_hiệu",
                    VisitPhoto.ocr_text.isnot(None),
                ).limit(1)
            )
            photo = res.scalar_one_or_none()
            if photo and photo.ocr_text:
                return f"\nTên từ biển hiệu (OCR): {photo.ocr_text[:200]}"
    except Exception:
        pass
    return ""
