#!/usr/bin/env python3
"""
🔧 LangChain Tools для RAG системы
Обертки вокруг существующих функций hybrid_search, graph_search и т.д.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
import chromadb
from chromadb.config import Settings as ChromaSettings
import os

from core.hybrid_bm25_search import hybrid_search
from core.graph_enhanced_search import GraphEnhancedHybridSearch

logger = logging.getLogger(__name__)


# Глобальные переменные для ChromaDB и Neo4j соединений
_chroma_collection = None
_graph_search_engine = None


async def get_chroma_collection():
    """Получить ChromaDB collection (singleton pattern)"""
    global _chroma_collection

    if _chroma_collection is None:
        try:
            client = await chromadb.AsyncHttpClient(
                host=os.getenv("CHROMA_HOST", "localhost"),
                port=int(os.getenv("CHROMA_PORT", 8000)),
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            _chroma_collection = await client.get_collection(
                name=os.getenv("COLLECTION_NAME", "documents")
            )
            logger.info("✅ ChromaDB collection connected")
        except Exception as e:
            logger.error(f"❌ Error connecting to ChromaDB: {e}")
            raise

    return _chroma_collection


async def get_graph_search_engine():
    """Получить Graph Search Engine (singleton pattern)"""
    global _graph_search_engine

    if _graph_search_engine is None:
        try:
            _graph_search_engine = GraphEnhancedHybridSearch()
            await _graph_search_engine.connect()
            logger.info("✅ Neo4j graph search connected")
        except Exception as e:
            logger.error(f"❌ Error connecting to Neo4j: {e}")
            # Не падаем - просто будем работать без графа
            return None

    return _graph_search_engine


@tool
async def hybrid_rag_search_tool(
    query: str,
    max_results: int = 5,
    law_filter: Optional[str] = None
) -> str:
    """
    Гибридный поиск BM25 + Semantic в ChromaDB.
    Используется для основного поиска по базе знаний.

    Args:
        query: Поисковый запрос
        max_results: Максимальное количество результатов (по умолчанию 5)
        law_filter: Фильтр по закону (если нужно)

    Returns:
        JSON-строка с результатами поиска
    """
    try:
        collection = await get_chroma_collection()

        # Выполняем hybrid search
        results = await hybrid_search(
            chromadb_collection=collection,
            query=query,
            k=max_results
        )

        # Фильтруем по закону если указан
        if law_filter:
            results = [r for r in results if r.get('metadata', {}).get('law_number') == law_filter]

        # Форматируем для LLM
        formatted_results = []
        for i, result in enumerate(results[:max_results], 1):
            formatted_results.append({
                "rank": i,
                "score": round(result['hybrid_score'], 3),
                "law": result['metadata'].get('law_number', 'N/A'),
                "article": result['metadata'].get('article_number', 'N/A'),
                "text": result['text'][:500]  # Первые 500 символов
            })

        return json.dumps(formatted_results, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"❌ Error in hybrid_rag_search_tool: {e}")
        return json.dumps({"error": str(e)})


@tool
async def graph_traversal_search_tool(
    article_numbers: List[str],
    law: str = "",
    depth: int = 1
) -> str:
    """
    Поиск связанных статей через Neo4j граф.
    Находит статьи, связанные через REFERENCES, RELATED_TO, DEFINES.

    Args:
        article_numbers: Список номеров статей для начала обхода
        law: Идентификатор закона (если нужен фильтр)
        depth: Глубина обхода графа (1 или 2)

    Returns:
        JSON-строка с найденными связанными статьями
    """
    try:
        graph_engine = await get_graph_search_engine()
        if not graph_engine:
            return json.dumps({"error": "Neo4j not available"})

        # TODO: Реализовать метод get_related_articles в GraphEnhancedHybridSearch
        # Пока заглушка
        related_articles = []

        return json.dumps(related_articles, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"❌ Error in graph_traversal_search_tool: {e}")
        return json.dumps({"error": str(e)})


@tool
async def definition_lookup_tool(term: str) -> str:
    """
    Специализированный поиск определений с LLM reranking.

    Стратегия:
    1. Множественные поисковые запросы
    2. Hybrid search с k=20
    3. LLM reranking

    Args:
        term: Термин для поиска определения

    Returns:
        JSON-строка с найденным определением
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        collection = await get_chroma_collection()

        # Множественные запросы
        search_queries = [
            f"{term} понимается является определение",
            f"что такое {term}",
            f"{term} далее",
            f'"{term}"',
            f"понятие {term}"
        ]

        logger.info(f"Definition lookup для '{term}' с {len(search_queries)} запросами")

        # Собираем результаты
        all_results = []
        for query in search_queries:
            results = await hybrid_search(
                chromadb_collection=collection,
                query=query,
                k=20
            )
            all_results.extend(results)

        # Удаляем дубликаты
        unique_results = {}
        for r in all_results:
            if r['id'] not in unique_results or r['hybrid_score'] > unique_results[r['id']]['hybrid_score']:
                unique_results[r['id']] = r

        results_list = list(unique_results.values())
        logger.info(f"Найдено {len(results_list)} уникальных результатов")

        if not results_list:
            return json.dumps({"error": f"No results found for '{term}'"})

        # Топ-15 для LLM
        results_list.sort(key=lambda x: x['hybrid_score'], reverse=True)
        top_results = results_list[:15]

        # LLM Reranking: используем Flash Lite + ротацию ключей
        from core.api_key_manager import get_key_manager
        key_manager = get_key_manager()
        llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_FLASH_LITE_MODEL", "gemini-2.5-flash-lite-preview-09-2025"),
            google_api_key=key_manager.get_next_key(),
            temperature=0
        )

        candidates_text = []
        for i, r in enumerate(top_results, 1):
            law = r['metadata'].get('law_number', 'N/A')
            article = r['metadata'].get('article_number', 'N/A')
            text_preview = r['text'][:600]
            candidates_text.append(f"\n[{i}] Закон: {law}, Статья: {article}\nТекст:\n{text_preview}\n")

        prompt = f"""Ты - эксперт по российскому законодательству.

Найди ТОЧНОЕ ОПРЕДЕЛЕНИЕ термина "{term}" среди этих фрагментов:

{chr(10).join(candidates_text)}

Верни ТОЛЬКО номер [N] (от 1 до {len(top_results)}) с определением "{term}".
Если определения нет - верни "0".

Ответ (только цифра):"""

        response = await llm.ainvoke(prompt)
        choice = response.content.strip()
        logger.info(f"LLM выбрал: {choice}")

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(top_results):
                best_result = top_results[choice_num - 1]
                result = {
                    "term": term,
                    "definition": best_result['text'],
                    "law": best_result['metadata'].get('law_number', 'N/A'),
                    "article": best_result['metadata'].get('article_number', 'N/A'),
                    "paragraph": best_result['metadata'].get('paragraph_number', 'N/A'),
                    "score": round(best_result['hybrid_score'], 3),
                    "llm_rank": choice_num
                }
                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                return json.dumps({"error": f"Definition not found (LLM returned {choice_num})"})
        except ValueError:
            # Fallback
            if top_results:
                return json.dumps({
                    "term": term,
                    "definition": top_results[0]['text'],
                    "law": top_results[0]['metadata'].get('law_number', 'N/A'),
                    "article": top_results[0]['metadata'].get('article_number', 'N/A'),
                    "score": round(top_results[0]['hybrid_score'], 3)
                }, ensure_ascii=False, indent=2)
            return json.dumps({"error": f"Definition for '{term}' not found"})

    except Exception as e:
        logger.error(f"Error in definition_lookup_tool: {e}")
        return json.dumps({"error": str(e)})


# Список всех доступных инструментов
RAG_TOOLS = [
    hybrid_rag_search_tool,
    graph_traversal_search_tool,
    definition_lookup_tool
]
