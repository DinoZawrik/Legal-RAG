#!/usr/bin/env python3
"""
LangGraph RAG Workflow (CRAG-inspired) - МИГРАЦИЯ v2.0

Многоступенчатый ретривел с оценкой качества и критикой ответа.
1. Первичный сбор: граф + быстрий гибридный поиск
2. Грейдинг документов, решение о доизвлечении
3. Ретрай/усиление запроса (CRAG repair) + веб-поиск при необходимости
4. Генерация ответа с минимальными вызовами OpenAI GPT-4 (МИГРАЦИЯ v2.0)
5. Критика ответа (self-check) и при необходимости повторный цикл

МИГРАЦИЯ v2.0 (13.10.2025):
- ChatGoogleGenerativeAI ChatOpenAI
- Gemini API key manager OpenAI API key manager
- Удалена зависимость от GeminiRateLimiter
"""

import asyncio
import json
import logging
import os
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from langgraph.graph import StateGraph, END

# МИГРАЦИЯ v3.0: OpenRouter (Nemotron) вместо OpenAI GPT-4
from langchain_openai import ChatOpenAI
# LEGACY: from langchain_google_genai import ChatGoogleGenerativeAI

from core.api_key_manager import get_key_manager
# LEGACY: from core.gemini_rate_limiter import GeminiRateLimiter

from core.hybrid_bm25_search import hybrid_search
from tools.rag_tools import get_chroma_collection
from tools.graph_tools import graph_definition_lookup
from tools.web_tools import web_legal_search
from core.reranker import get_reranker, convert_to_dict

logger = logging.getLogger(__name__)

# МИГРАЦИЯ v2.0: OpenAI key manager
_key_manager = get_key_manager(provider="openai")

# Reranker instance (singleton)
_reranker = None


class AgentState(TypedDict):
    query: str
    reformulated_query: str
    definition_result: Optional[Dict[str, Any]]
    primary_results: List[Dict[str, Any]]
    rag_results: List[Dict[str, Any]]
    web_results: List[Dict[str, Any]]
    final_answer: str
    sources: List[Dict[str, Any]]
    reasoning_trace: List[str]
    quality_flags: List[str]
    needs_repair: bool
    retry_count: int


def _extract_candidate_term(query: str) -> Optional[str]:
    q = query.strip().lower()
    prefixes = ["что такое", "понятие", "определение", "кто такой", "что означает"]
    for prefix in prefixes:
        if q.startswith(prefix):
            candidate = query[len(prefix):].strip(" ?!\"")
            return candidate or None
    if 3 <= len(query.split()) <= 6:
        return query.strip(" ?!\"")
    return None


def _detect_law_filter(query: str) -> Optional[str]:
    return None


async def _run_hybrid_search(
    query: str,
    k: int = 10,
    law_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    collection = await get_chroma_collection()
    raw_results = await hybrid_search(collection, query=query, k=k)

    results: List[Dict[str, Any]] = []
    for item in raw_results or []:
        if isinstance(item, dict):
            results.append(item)
            continue

        if is_dataclass(item):
            data = asdict(item)
        else:
            data = {
                key: getattr(item, key)
                for key in dir(item)
                if not key.startswith("_")
                and not callable(getattr(item, key))
            }

        if "metadata" not in data or data["metadata"] is None:
            data["metadata"] = {}
        if "text" not in data or data["text"] is None:
            data["text"] = ""
        if "doc_id" in data and "id" not in data:
            data["id"] = data["doc_id"]

        results.append(data)

    if law_filter:
        filtered = [r for r in results if r.get("metadata", {}).get("law_number") == law_filter]
        if filtered:
            return filtered
    return results


def _parse_graph_response(graph_raw: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if isinstance(graph_raw, Exception):
        return None, f"Graph lookup failed: {graph_raw}"

    parsed = None
    if isinstance(graph_raw, str):
        try:
            parsed = json.loads(graph_raw)
        except json.JSONDecodeError:
            return None, f"Graph response parse error: {graph_raw}"
    elif isinstance(graph_raw, dict):
        parsed = graph_raw
    else:
        parsed = graph_raw

    if isinstance(parsed, dict) and parsed.get("found"):
        results = parsed.get("results", [])
        if results:
            return results[0], "Graph definition found"
    if isinstance(parsed, dict) and parsed.get("error"):
        return None, f"Graph response error: {parsed['error']}"
    return None, None


def _merge_results(primary: List[Dict[str, Any]], extra: List[Dict[str, Any]], max_results: int = 15) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()

    def _make_key(item: Dict[str, Any]) -> Tuple[str, str]:
        metadata = item.get("metadata", {})
        doc_id = (
            item.get("doc_id")
            or item.get("id")
            or metadata.get("document_id")
            or metadata.get("source_id")
        )
        if doc_id:
            return ("doc", str(doc_id))
        text = (item.get("text") or "")[:120]
        return ("text", text)

    for candidate in primary + extra:
        key = _make_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        merged.append(candidate)
        if len(merged) >= max_results:
            break
    return merged


def _grade_rag_results(results: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool, List[str]]:
    if not results:
        return [], True, ["no_results"]

    filtered: List[Dict[str, Any]] = []
    for item in results:
        text = (item.get("text") or "").strip()
        score = item.get("hybrid_score") or item.get("semantic_score") or 0.0
        metadata = item.get("metadata", {})
        has_article = bool(metadata.get("article_number") or metadata.get("article"))
        if len(text) >= 180 or (score and score >= 0.45) or has_article:
            filtered.append(item)

    flags: List[str] = []
    if not filtered:
        flags.append("no_relevant_hits")
        filtered = results[: min(3, len(results))]
    elif len(filtered) < 2:
        flags.append("low_coverage")

    need_more = bool(flags)
    return filtered, need_more, flags


def _transform_query(original_query: str, flags: List[str], attempt: int) -> str:
    additions: List[str] = []
    lower_flags = set(flags)
    if "no_relevant_hits" in lower_flags:
        additions.append("юридическое определение")
    if "low_coverage" in lower_flags:
        additions.append("подробное описание")
    if "missing_citation" in lower_flags or attempt > 0:
        additions.append("укажите статьи и нормы права")

    addition_text = " ".join(additions)
    if addition_text:
        return f"{original_query} {addition_text}".strip()
    if attempt > 0:
        return f"{original_query} правовое регулирование".strip()
    return original_query


async def _perform_web_search(query: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    try:
        raw = await web_legal_search.ainvoke({"query": query})
    except Exception as exc:
        return [], f"Web search failed: {exc}"

    parsed: Any = raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return [], f"Web response parse error"

    results: List[Dict[str, Any]] = []
    if isinstance(parsed, dict):
        if parsed.get("found"):
            results = parsed.get("results", [])
        elif isinstance(parsed.get("results"), list):
            results = parsed["results"]
        elif parsed.get("error"):
            return [], f"Web search error: {parsed['error']}"
    elif isinstance(parsed, list):
        results = parsed

    return results[:5], None


class LangGraphRAGWorkflow:
    def __init__(self, api_key: Optional[str] = None, use_reranker: bool = True):
        """
        МИГРАЦИЯ v2.0: Инициализация с OpenAI GPT-4 Turbo (готовность к GPT-5).

        Args:
            api_key: OpenAI API key (optional, берется из manager)
            use_reranker: Enable BGE reranker (default True)
        """
        self.api_key = api_key or _key_manager.get_next_key()

        # МИГРАЦИЯ v3.0: OpenRouter Nemotron (бесплатный, 120B параметров)
        # Используем OpenRouter API (совместим с OpenAI SDK)
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        openrouter_base = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        openrouter_model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")

        self.answer_llm = ChatOpenAI(
            model=openrouter_model,
            openai_api_key=openrouter_key,
            openai_api_base=openrouter_base,
            temperature=0.2,
            max_tokens=2048,
            max_retries=3
        )

        # Reranker (BGE v2-m3, бесплатный open-source)
        self.use_reranker = use_reranker
        if use_reranker:
            global _reranker
            if _reranker is None:
                _reranker = get_reranker(reranker_type="bge", use_reranker=True)
            self.reranker = _reranker
        else:
            self.reranker = get_reranker(reranker_type="noop", use_reranker=False)

        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(AgentState)
        workflow.add_node("retrieve_initial", self._retrieve_initial_node)
        workflow.add_node("grade_documents", self._grade_documents_node)
        workflow.add_node("repair_retrieve", self._repair_retrieve_node)
        workflow.add_node("generate_answer", self._generate_answer_node)
        workflow.add_node("critique_answer", self._critique_answer_node)

        workflow.set_entry_point("retrieve_initial")
        workflow.add_edge("retrieve_initial", "grade_documents")
        workflow.add_conditional_edges(
            "grade_documents",
            self._decide_after_grade,
            {
                "repair": "repair_retrieve",
                "generate": "generate_answer",
            },
        )
        workflow.add_edge("repair_retrieve", "generate_answer")
        workflow.add_edge("generate_answer", "critique_answer")
        workflow.add_conditional_edges(
            "critique_answer",
            self._decide_after_critique,
            {
                "retry": "repair_retrieve",
                "end": END,
            },
        )
        return workflow.compile()

    async def _retrieve_initial_node(self, state: AgentState) -> AgentState:
        query = state["query"]
        candidate_term = _extract_candidate_term(query)
        law_filter = _detect_law_filter(query)

        hybrid_task = _run_hybrid_search(query, k=10, law_filter=law_filter)
        graph_task = (
            graph_definition_lookup.ainvoke({"term": candidate_term})
            if candidate_term
            else asyncio.sleep(0, result=None)
        )

        rag_results_raw, graph_raw = await asyncio.gather(
            hybrid_task,
            graph_task,
            return_exceptions=True,
        )

        primary_results: List[Dict[str, Any]] = []
        if isinstance(rag_results_raw, Exception):
            state["reasoning_trace"].append(
                f"Hybrid search error: {rag_results_raw}"
            )
        else:
            primary_results = rag_results_raw or []
            state["reasoning_trace"].append(
                f"Initial retrieval returned {len(primary_results)} candidates"
            )

            # НОВОЕ: Reranking после hybrid search
            if self.use_reranker and len(primary_results) > 5:
                try:
                    reranked = await self.reranker.rerank(
                        query=query,
                        documents=primary_results,
                        top_k=10, # Берем top-10 после rerank
                        combine_weight=0.6 # 60% rerank score, 40% original hybrid score
                    )

                    # Convert back to dict format
                    primary_results = convert_to_dict(reranked)

                    state["reasoning_trace"].append(
                        f"Reranked {len(reranked)} documents (BGE Reranker v2-m3)"
                    )
                except Exception as e:
                    # Reranker failed, continue with original results
                    logger.warning(f"Reranking failed, using original results: {e}")
                    state["reasoning_trace"].append(
                        f"Reranking skipped (error: {str(e)[:50]})"
                    )

        definition, message = _parse_graph_response(graph_raw)
        if definition:
            state["definition_result"] = definition
        if message:
            state["reasoning_trace"].append(message)

        state["primary_results"] = primary_results
        state["rag_results"] = primary_results[:]
        state["needs_repair"] = False
        state.setdefault("web_results", [])
        return state

    async def _grade_documents_node(self, state: AgentState) -> AgentState:
        filtered, need_more, flags = _grade_rag_results(state.get("rag_results", []))
        state["rag_results"] = filtered
        state["needs_repair"] = need_more
        state["quality_flags"] = flags
        if filtered:
            state["reasoning_trace"].append(
                f"Graded {len(filtered)} documents (flags: {', '.join(flags) if flags else 'none'})"
            )
        else:
            state["reasoning_trace"].append("No documents after grading")
        return state

    async def _repair_retrieve_node(self, state: AgentState) -> AgentState:
        attempt = state.get("retry_count", 0)
        base_query = state.get("reformulated_query") or state["query"]
        new_query = _transform_query(base_query, state.get("quality_flags", []), attempt)
        state["reformulated_query"] = new_query

        law_filter = _detect_law_filter(new_query)
        augmented_results = await _run_hybrid_search(new_query, k=18, law_filter=law_filter)
        merged_results = _merge_results(state.get("rag_results", []), augmented_results)
        filtered, need_more, flags = _grade_rag_results(merged_results)

        state["primary_results"] = merged_results
        state["rag_results"] = filtered
        state["quality_flags"] = flags
        state["needs_repair"] = need_more
        state["retry_count"] = attempt + 1

        state["reasoning_trace"].append(
            f"Repair retrieval attempt {state['retry_count']} yielded {len(merged_results)} docs (flags: {', '.join(flags) if flags else 'none'})"
        )

        candidate_term = _extract_candidate_term(new_query)
        if not state.get("definition_result") and candidate_term:
            definition, message = _parse_graph_response(
                await graph_definition_lookup.ainvoke({"term": candidate_term})
            )
            if definition:
                state["definition_result"] = definition
            if message:
                state["reasoning_trace"].append(message)

        if need_more or "no_results" in flags:
            web_results, web_message = await _perform_web_search(new_query)
            state["web_results"] = web_results
            if web_message:
                state["reasoning_trace"].append(web_message)
            else:
                state["reasoning_trace"].append(
                    f"Web search added {len(web_results)} results"
                )
        else:
            state["web_results"] = state.get("web_results", [])
            state["reasoning_trace"].append("Web search not required after repair")

        return state

    async def _generate_answer_node(self, state: AgentState) -> AgentState:
        query = state["reformulated_query"] or state["query"]
        definition = state.get("definition_result")
        rag_results = state.get("rag_results", [])
        web_results = state.get("web_results", [])

        context_parts: List[str] = []
        if definition:
            context_parts.append("ОПРЕДЕЛЕНИЕ:")
            context_parts.append(definition.get("definition", ""))
            source = definition.get("source") or definition.get("law")
            if source:
                context_parts.append(f"Источник: {source}")

        for hit in rag_results[:5]:
            metadata = hit.get("metadata", {})
            law = metadata.get("law_number") or metadata.get("document_number") or "N/A"
            article = metadata.get("article_number") or metadata.get("article") or ""
            snippet = (hit.get("text", "") or "")[:400]
            label = f"VECTOR [{law}{f' ст.{article}' if article else ''}]"
            context_parts.append(f"{label}: {snippet}")

        for web in web_results[:3]:
            title = web.get("title", "")
            snippet = (web.get("snippet", "") or "")[:400]
            context_parts.append(f"WEB {title}: {snippet}")

        if not context_parts:
            context_parts.append("(Нет дополнительных данных, ответь по общим знаниям)")

        context = "\n\n".join(context_parts)
        prompt = f"""
Ты — юридический ассистент по российскому праву.
Вопрос клиента: {query}

Используй приведённые материалы:
{context}

Сформулируй ответ кратко (3-5 предложений), указывая статьи и законы, если цитируешь их.
"""

        # МИГРАЦИЯ v2.0: Упрощенная генерация через OpenAI (без ротации ключей и rate limiting)
        final_answer = ""
        last_error: Optional[Exception] = None

        # OpenAI не требует такой частой ротации как Gemini
        for retry in range(3): # 3 попытки при ошибках
            try:
                # OpenAI SDK имеет встроенный retry, поэтому не нужен GeminiRateLimiter
                response = await self.answer_llm.ainvoke(prompt)
                final_answer = response.content
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()

                state["reasoning_trace"].append(f"Answer generation error (attempt {retry + 1}/3): {exc}")

                # Retry только для network/timeout ошибок
                if "timeout" in message or "connection" in message:
                    await asyncio.sleep(2 ** retry) # Exponential backoff
                    continue
                else:
                    # Другие ошибки - сразу прерываем
                    raise

        # LEGACY: Gemini ротация ключей
        # for _ in range(len(_key_manager.API_KEYS)):
        # answer_key = _key_manager.get_next_key()
        # self.answer_llm = ChatGoogleGenerativeAI(
        # model="gemini-2.5-flash-preview-09-2025",
        # google_api_key=answer_key,
        # temperature=0.2,
        # )
        # try:
        # await GeminiRateLimiter.wait("flash")
        # response = await self.answer_llm.ainvoke(prompt)
        # final_answer = response.content
        # last_error = None
        # break
        # except Exception as exc:
        # last_error = exc
        # message = str(exc).lower()
        # quota_error = "quota" in message or "429" in message
        # _key_manager.report_error(answer_key, is_quota_error=quota_error)
        # state["reasoning_trace"].append(
        # "Answer generation quota hit, rotating key" if quota_error else f"Answer generation error: {exc}"
        # )
        # if quota_error:
        # await asyncio.sleep(2)
        # continue
        # raise

        if last_error:
            raise last_error

        sources: List[Dict[str, Any]] = []
        if definition:
            sources.append(
                {
                    "type": "definition",
                    "source": definition.get("source") or definition.get("law"),
                    "article": definition.get("article"),
                }
            )
        for hit in rag_results[:3]:
            metadata = hit.get("metadata", {})
            sources.append(
                {
                    "type": "rag",
                    "law": metadata.get("law_number") or metadata.get("document_number"),
                    "article": metadata.get("article_number") or metadata.get("article"),
                    "score": hit.get("hybrid_score") or hit.get("bm25_score"),
                }
            )
        for web in web_results[:2]:
            sources.append(
                {
                    "type": "web",
                    "title": web.get("title"),
                    "url": web.get("url"),
                }
            )

        state["final_answer"] = final_answer
        state["sources"] = sources
        state["reasoning_trace"].append("Answer generated")
        return state

    async def _critique_answer_node(self, state: AgentState) -> AgentState:
        answer = (state.get("final_answer") or "").strip()
        sources = state.get("sources", [])
        issues: List[str] = []

        if not answer:
            issues.append("empty_answer")
        if not sources:
            issues.append("no_sources")
        if sources and "статья" not in answer.lower():
            issues.append("missing_citation")

        if issues:
            state["quality_flags"] = list({*state.get("quality_flags", []), *issues})
            state["needs_repair"] = True
            state["reasoning_trace"].append(
                f"Critique flagged issues: {', '.join(issues)}"
            )
        else:
            state["needs_repair"] = False
            state["reasoning_trace"].append("Critique passed")
        return state

    def _decide_after_grade(self, state: AgentState) -> str:
        return "repair" if state.get("needs_repair") else "generate"

    def _decide_after_critique(self, state: AgentState) -> str:
        if state.get("needs_repair") and state.get("retry_count", 0) < 2:
            return "retry"
        return "end"

    async def run(self, query: str) -> Dict[str, Any]:
        initial_state: AgentState = {
            "query": query,
            "reformulated_query": query,
            "definition_result": None,
            "primary_results": [],
            "rag_results": [],
            "web_results": [],
            "final_answer": "",
            "sources": [],
            "reasoning_trace": [],
            "quality_flags": [],
            "needs_repair": False,
            "retry_count": 0,
        }

        final_state = await self.workflow.ainvoke(initial_state)

        source_type = "rag"
        if final_state.get("web_results"):
            source_type = "web"
        if final_state.get("definition_result"):
            source_type = "definition"

        confidence = 0.4
        if final_state.get("definition_result"):
            confidence = 0.75
        elif final_state.get("rag_results"):
            confidence = 0.6
        elif final_state.get("web_results"):
            confidence = 0.5

        return {
            "answer": final_state.get("final_answer", ""),
            "sources": final_state.get("sources", []),
            "source_type": source_type,
            "confidence": confidence,
            "reasoning_trace": final_state.get("reasoning_trace", []),
            "quality_flags": final_state.get("quality_flags", []),
            "retry_count": final_state.get("retry_count", 0),
        }
