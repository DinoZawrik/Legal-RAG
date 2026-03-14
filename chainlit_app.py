"""
LegalRAG — Chainlit Chat Interface

Интерактивный чат-интерфейс с пошаговой визуализацией RAG pipeline:
- Гибридный поиск (BM25 + Semantic + Graph)
- Визуализация каждого шага workflow
- Отображение источников и confidence
- Загрузка документов через drag-and-drop
"""

import os
import sys
import json
import time
import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
import chainlit as cl

logger = logging.getLogger(__name__)

# API Gateway URL
API_BASE_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080")


# Startup

@cl.on_chat_start
async def on_chat_start():
    """Initialize chat session."""
    # Pre-check API health silently
    await _check_api_health()


@cl.set_starters
async def set_starters():
    """Quick-start examples."""
    return [
        cl.Starter(
            label="Определение",
            message="Что такое трудовой договор согласно Трудовому кодексу РФ?",
            icon="/public/icons/definition.svg",
        ),
        cl.Starter(
            label="Сроки и цифры",
            message="Какой максимальный срок испытания при приёме на работу?",
            icon="/public/icons/time.svg",
        ),
        cl.Starter(
            label="Сравнительный анализ",
            message="Сравните права работника при увольнении по собственному желанию и по сокращению штата",
            icon="/public/icons/compare.svg",
        ),
        cl.Starter(
            label="Порядок действий",
            message="Какой порядок обжалования решения суда в апелляционной инстанции?",
            icon="/public/icons/procedure.svg",
        ),
    ]


# Message Handler

@cl.on_message
async def on_message(message: cl.Message):
    """Process user query with step-by-step RAG visualization."""
    query = message.content.strip()
    if not query:
        return

    # Handle file uploads
    if message.elements:
        await _handle_file_upload(message)
        return

    start_time = time.time()
    response_msg = cl.Message(content="")
    await response_msg.send()

    try:
        result = await _process_query_with_steps(query, response_msg)

        if not result:
            response_msg.content = "Не удалось получить ответ. Проверьте, что API Gateway запущен."
            await response_msg.update()
            return

        # Format final answer
        answer = result.get("answer", "Ответ не получен")
        # Strip trailing "Источник(и)" section from LLM answer (we show them separately)
        import re
        answer = re.split(r'\n+(?:\*{0,2})Источник[и]?(?:\*{0,2})\s*(?:\:|\n)', answer, maxsplit=1)[0].rstrip()
        sources = result.get("sources", [])
        metadata = result.get("metadata", {})
        confidence = _extract_confidence(result)
        elapsed = time.time() - start_time

        # Build response
        response_parts = [answer, ""]

        # Sources
        if sources:
            response_parts.append("---")
            seen = set()
            displayed = []
            for src in sources[:5]:
                src_text = _format_source(src)
                if src_text and src_text not in seen:
                    seen.add(src_text)
                    displayed.append(src_text)
            response_parts.append(f"**Источники** ({len(displayed)}):")
            response_parts.append("")
            for i, src_text in enumerate(displayed, 1):
                response_parts.append(f"{i}. {src_text}")

        # Confidence badge + timing
        badge = _confidence_badge(confidence)
        response_parts.append("")
        response_parts.append("---")
        model_name = metadata.get('model_used', 'AI')
        total_time = metadata.get('total_time', elapsed)
        response_parts.append(
            f"{badge} | {total_time:.1f}с | {result.get('chunks_used', '?')} фрагментов | {model_name}"
        )

        response_msg.content = "\n".join(response_parts)
        await response_msg.update()

    except Exception as e:
        logger.exception("Error processing query")
        response_msg.content = f"Ошибка: {e}"
        await response_msg.update()


# Query Processing with Step Visualization

async def _process_query_with_steps(query: str, parent_msg: cl.Message) -> Optional[Dict[str, Any]]:
    """Execute RAG pipeline with Chainlit step visualization."""

    # Step 1: Query Analysis
    async with cl.Step(name="Анализ запроса", type="tool") as step:
        step.input = query
        query_info = _analyze_query(query)
        step.output = (
            f"**Тип:** {query_info['type']}\n"
            f"**Ключевые термины:** {', '.join(query_info['terms'])}\n"
            f"**Стратегия:** {query_info['strategy']}"
        )

    # Step 2: Hybrid Search (BM25 + Semantic + Graph)
    async with cl.Step(name="Гибридный поиск", type="retrieval") as step:
        step.input = f"Запрос: {query}\nСтратегия: BM25 (50%) + Semantic (50%) + Graph enrichment"

        search_start = time.time()
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(
                    f"{API_BASE_URL}/api/query",
                    json={
                        "query": query,
                        "max_results": 10,
                        "use_cache": True,
                        "config": {
                            "search_config": {
                                "use_graph": True,
                                "use_bm25": True,
                                "use_reranker": True,
                            }
                        },
                    },
                )
        except httpx.ConnectError:
            step.output = "API Gateway недоступен"
            return None
        except httpx.ReadTimeout:
            step.output = "Таймаут запроса (>90с)"
            return None

        search_time = time.time() - search_start

        if resp.status_code != 200:
            step.output = f"Ошибка API: {resp.status_code} — {resp.text[:200]}"
            return None

        result = resp.json()

        # Extract search details
        sources = result.get("sources", result.get("source_documents", []))
        chunks_used = result.get("chunks_used", len(sources))

        # Use actual search time from API metadata, not total round-trip
        api_search_time = result.get('metadata', {}).get('search_time', search_time)
        if api_search_time < 1:
            search_display = f"{api_search_time*1000:.0f}мс"
        else:
            search_display = f"{api_search_time:.1f}с"

        search_output = [
            f"Найдено **{chunks_used}** релевантных фрагментов за **{search_display}**",
            "",
        ]

        # Group chunks by source, keep best score & preview per source
        seen_sources: dict[str, tuple[float, str]] = {}  # ref -> (best_sim, best_preview)
        for src in sources:
            if isinstance(src, dict):
                ref = _format_source(src)
                if not ref:
                    continue
                sim = src.get("similarity", src.get("hybrid_score", src.get("distance", 0)))
                text_preview = (src.get("text", src.get("document", src.get("content", "")))[:120] or "").replace("\n", " ")
                if ref not in seen_sources or sim > seen_sources[ref][0]:
                    seen_sources[ref] = (sim, text_preview)

        for i, (ref, (sim, text_preview)) in enumerate(seen_sources.items(), 1):
            if i > 3:
                break
            score_str = f" (сходство: {sim:.2f})" if sim > 0 else ""
            search_output.append(f"**{i}.** `{ref}`{score_str}")
            if text_preview:
                search_output.append(f"  _{text_preview}..._")

        step.output = "\n".join(search_output)

    # Step 3: Verification & Quality Assessment (merged)
    async with cl.Step(name="Верификация и оценка", type="tool") as step:
        confidence = _extract_confidence(result)
        verification = result.get("verification", {})
        model = result.get("metadata", {}).get("model_used", "gemini-3-flash-preview")
        inference_time = result.get("metadata", {}).get("inference_time", 0)
        step.input = f"Проверка {chunks_used} фрагментов · {model}"

        # Confidence level
        if confidence >= 0.7:
            level = "Высокая"
        elif confidence >= 0.4:
            level = "Средняя"
        else:
            level = "Низкая"

        lines = [f"**Достоверность:** {confidence:.0%} ({level})"]

        if verification:
            cit_acc = verification.get('citation_accuracy', 0)
            sup_rate = verification.get('support_rate', 0)
            lines.append(f"**Точность цитат:** {cit_acc:.0%} · **Поддержка утверждений:** {sup_rate:.0%}")

        lines.append(f"**Модель:** {model} · **Генерация:** {inference_time:.1f}с")
        step.output = "\n".join(lines)

    return result


# File Upload Handler

async def _handle_file_upload(message: cl.Message):
    """Handle document uploads via chat."""
    for element in message.elements:
        if not hasattr(element, "path") or not element.path:
            continue

        filename = getattr(element, "name", "document")
        file_path = element.path

        async with cl.Step(name=f"Загрузка: {filename}", type="tool") as step:
            step.input = f"Файл: {filename}\nПуть: {file_path}"

            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    with open(file_path, "rb") as f:
                        resp = await client.post(
                            f"{API_BASE_URL}/api/upload",
                            files={"file": (filename, f)},
                            data={
                                "original_filename": filename,
                                "document_type": "regulatory",
                                "async_processing": "false",
                            },
                        )

                if resp.status_code == 200:
                    data = resp.json()
                    chunks = data.get("chunks_created", 0)
                    doc_id = data.get("document_id", "N/A")
                    step.output = (
                        f"Документ обработан\n"
                        f"**ID:** {doc_id}\n"
                        f"**Чанков создано:** {chunks}\n"
                        f"**Дубликат:** {'Да' if data.get('duplicate') else 'Нет'}"
                    )
                    await cl.Message(
                        content=f"**{filename}** загружен и обработан ({chunks} чанков). Теперь вы можете задавать вопросы по этому документу."
                    ).send()
                else:
                    step.output = f"Ошибка загрузки: {resp.status_code}"
                    await cl.Message(content=f"Ошибка загрузки {filename}: {resp.text[:200]}").send()

            except Exception as e:
                step.output = f"{e}"
                await cl.Message(content=f"Ошибка при загрузке {filename}: {e}").send()


# Helpers

async def _check_api_health() -> Optional[Dict[str, Any]]:
    """Check API Gateway health."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{API_BASE_URL}/info")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return None


def _analyze_query(query: str) -> Dict[str, Any]:
    """Simple client-side query analysis for step visualization."""
    q_lower = query.lower()
    terms = [w for w in query.split() if len(w) > 3][:5]

    if any(q_lower.startswith(p) for p in ["что такое", "определение", "понятие"]):
        return {"type": "Определение", "terms": terms, "strategy": "Graph lookup + Semantic search"}
    elif any(w in q_lower for w in ["сравн", "отлич", "разниц"]):
        return {"type": "Сравнение", "terms": terms, "strategy": "Multi-document retrieval + Synthesis"}
    elif any(w in q_lower for w in ["срок", "когда", "сколько"]):
        return {"type": "Фактический вопрос", "terms": terms, "strategy": "Exact match + BM25 boost"}
    elif any(w in q_lower for w in ["порядок", "процедур", "как "]):
        return {"type": "Процедурный вопрос", "terms": terms, "strategy": "Sequential retrieval + Aggregation"}
    else:
        return {"type": "Общий вопрос", "terms": terms, "strategy": "Hybrid BM25 + Semantic + Graph"}


def _extract_confidence(result: Dict[str, Any]) -> float:
    """Extract confidence score from API response."""
    if "confidence" in result:
        return float(result["confidence"])
    verification = result.get("verification", {})
    if "confidence" in verification:
        return float(verification["confidence"])
    # Estimate from metadata
    chunks = result.get("chunks_used", 0)
    if chunks >= 3:
        return 0.7
    elif chunks >= 1:
        return 0.5
    return 0.3


def _confidence_badge(confidence: float) -> str:
    """Confidence indicator with level label."""
    pct = f"{confidence:.0%}"
    if confidence >= 0.7:
        return f"**Достоверность: {pct}** (высокая)"
    elif confidence >= 0.4:
        return f"**Достоверность: {pct}** (средняя)"
    else:
        return f"**Достоверность: {pct}** (требует проверки)"


# Маппинг английских названий документов на русские
_LAW_NAME_MAP = {
    "Consumer Protection Law": "Закон о защите прав потребителей",
    "consumer_protection_law": "Закон о защите прав потребителей",
    "Labor Code Excerpt": "Трудовой кодекс РФ",
    "labor_code_excerpt": "Трудовой кодекс РФ",
    "Labor Code": "Трудовой кодекс РФ",
    "Civil Code": "Гражданский кодекс РФ",
    "Criminal Code": "Уголовный кодекс РФ",
    "Tax Code": "Налоговый кодекс РФ",
    "Family Code": "Семейный кодекс РФ",
    # PDF filenames
    "skodeksrf.pdf": "Семейный кодекс РФ",
    "skodeksrf": "Семейный кодекс РФ",
    "garant_grajdansky_kodeks_rf.pdf": "Гражданский кодекс РФ",
    "garant_grajdansky_kodeks_rf": "Гражданский кодекс РФ",
    "grazhdanskij_kodeks_rf.pdf": "Гражданский кодекс РФ",
    "grazhdanskij_kodeks_rf": "Гражданский кодекс РФ",
    "semejnyj_kodeks_rf.pdf": "Семейный кодекс РФ",
    "semejnyj_kodeks_rf": "Семейный кодекс РФ",
    "labor_code_excerpt.pdf": "Трудовой кодекс РФ",
    "trudovoj_kodeks_rf": "Трудовой кодекс РФ",
    "trudovoj_kodeks_rf.pdf": "Трудовой кодекс РФ",
    "zakon_o_zashite_prav_potrebitelej": "Закон о защите прав потребителей",
    "consumer_protection_law.pdf": "Закон о защите прав потребителей",
    "zhilishchnyj_kodeks_rf": "Жилищный кодекс РФ",
}


def _translate_law_name(name: str) -> str:
    """Translate English law name to Russian if mapping exists."""
    if not name:
        return name
    # Exact match
    if name in _LAW_NAME_MAP:
        return _LAW_NAME_MAP[name]
    # Case-insensitive match
    name_lower = name.lower()
    for eng, rus in _LAW_NAME_MAP.items():
        if eng.lower() == name_lower:
            return rus
    # Strip extensions and retry
    base = name.replace('.txt', '').replace('.pdf', '')
    base_lower = base.lower()
    for eng, rus in _LAW_NAME_MAP.items():
        eng_base = eng.replace('.txt', '').replace('.pdf', '').lower()
        if eng_base == base_lower:
            return rus
    # Prefix match: filename may have hash suffix like "labor_code_excerpt_97c9cb59"
    for eng, rus in _LAW_NAME_MAP.items():
        eng_base = eng.replace('.txt', '').replace('.pdf', '').lower()
        if len(eng_base) > 3 and base_lower.startswith(eng_base):
            return rus
    return name


def _format_source(src: Any) -> str:
    """Format a single source for display."""
    if isinstance(src, dict):
        meta = src.get("metadata", {})
        law = _translate_law_name(meta.get("law", meta.get("law_number", "")))
        article = meta.get("article", meta.get("article_number", ""))
        doc_type = meta.get("type", meta.get("document_type", ""))

        # Fallback: extract law name from original_filename
        if not law:
            fname = meta.get("original_filename", meta.get("file_name", ""))
            law = _translate_law_name(fname)
            # If still just filename, try to make it human-readable
            if law == fname and fname:
                law = fname.replace('.pdf', '').replace('.txt', '').replace('_', ' ').title()

        # Fallback: extract article number from text
        if not article:
            text = src.get("text", src.get("document", src.get("content", "")))
            if text:
                import re
                m = re.match(r'Статья\s+(\d+[\.\d]*)', text.strip())
                if m:
                    article = m.group(1)

        parts = []
        if law:
            parts.append(str(law))
        if article:
            parts.append(f"ст. {article}")
        if doc_type and not law:
            parts.append(doc_type)

        if parts:
            return " · ".join(parts)
        # Fall back to text preview
        text = src.get("text", src.get("document", src.get("content", "")))
        if text:
            return text[:80].replace("\n", " ") + "..."
    return ""
