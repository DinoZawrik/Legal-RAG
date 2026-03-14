#!/usr/bin/env python3
"""
Lightweight web search fallback (DuckDuckGo, Bing scraping)
"""

import asyncio
import logging
import os
from typing import Any, Dict, List

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Import simple searches
try:
    from tools.duckduckgo_search import async_search_duckduckgo
    DUCKDUCKGO_AVAILABLE = True
except ImportError:
    DUCKDUCKGO_AVAILABLE = False
    logger.warning("DuckDuckGo search not available")

try:
    from tools.google_search import async_search_google
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google search not available")


class SimpleSearchResult(BaseModel):
    """Результат простого web поиска"""
    title: str = Field(description="Заголовок результата")
    snippet: str = Field(description="Краткое описание/выдержка")
    url: str = Field(description="URL страницы")
    source: str = Field(default="web", description="Источник: google/duckduckgo/консультант")


class SimpleSearchResults(BaseModel):
    """Список результатов поиска"""
    results: List[SimpleSearchResult] = Field(description="Результаты поиска")


async def search_google(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Простой поиск через Google с LLM extraction

    Args:
        query: Поисковый запрос
        max_results: Максимум результатов

    Returns:
        Список результатов с title, snippet, url
    """
    try:
        import urllib.parse

        # Google search URL
        enhanced_query = query
        encoded_query = urllib.parse.quote(enhanced_query)
        search_url = f"https://www.google.com/search?q={encoded_query}&num={max_results * 2}"

        logger.info(f"[GOOGLE] Searching: {enhanced_query}")

        # LLM extraction strategy
        from core.api_key_manager import get_key_manager
        key_manager = get_key_manager()
        gemini_key = key_manager.get_next_key()

        extraction_strategy = LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="gemini/gemini-2.5-flash-lite-preview-09-2025",
                api_token=gemini_key
            ),
            schema=SimpleSearchResults.model_json_schema(),
            extraction_type="schema",
            instruction=f"""Extract search results from Google search page.

            Look for ORGANIC search results only (NOT ads, NOT "People also ask").

            For each result extract:
            - title: Full title of the page
            - snippet: Description text shown in search result
            - url: Full URL

            Focus on results from:
            - consultant.ru (КонсультантПлюс)
            - garant.ru (Гарант)
            - government websites (.gov.ru)
            - legal information sites

            Exclude:
            - Advertisements (Реклама)
            - Related searches
            - "People also ask" blocks

            Query: "{query}"
            Return top {max_results} most relevant results.
            """,
            input_format="markdown",
            apply_chunking=False
        )

        # Crawl Google search results
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(
                url=search_url,
                delay_before_return_html=2.0,
                extraction_strategy=extraction_strategy,
                screenshot=False
            )

            if not result.success:
                logger.warning(f"[GOOGLE] Crawl failed: {result.error_message}")
                return []

            # Parse LLM extraction
            if result.extracted_content:
                import json
                try:
                    extracted = json.loads(result.extracted_content)

                    if isinstance(extracted, dict) and 'results' in extracted:
                        items = extracted['results']
                    elif isinstance(extracted, list):
                        items = extracted
                    else:
                        items = [extracted]

                    results = []
                    for item in items[:max_results]:
                        if isinstance(item, dict):
                            results.append({
                                'title': item.get('title', ''),
                                'snippet': item.get('snippet', ''),
                                'url': item.get('url', ''),
                                'source': 'google',
                                'extraction_method': 'llm'
                            })

                    logger.info(f"[GOOGLE] Found {len(results)} results")
                    return results

                except Exception as e:
                    logger.error(f"[GOOGLE] Extraction failed: {e}")
                    return []

            logger.warning("[GOOGLE] No extracted content")
            return []

    except Exception as e:
        logger.error(f"[GOOGLE] Search error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Простой поиск через DuckDuckGo (без отслеживания)

    Args:
        query: Поисковый запрос
        max_results: Максимум результатов

    Returns:
        Список результатов с title, snippet, url
    """
    try:
        import urllib.parse

        # DuckDuckGo HTML search (no JS required, privacy-friendly)
        enhanced_query = query
        encoded_query = urllib.parse.quote(enhanced_query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        logger.info(f"[DUCKDUCKGO] Searching: {enhanced_query}")

        # LLM extraction strategy
        extraction_strategy = LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="gemini/gemini-2.5-flash-lite-preview-09-2025",
                api_token=gemini_key
            ),
            schema=SimpleSearchResults.model_json_schema(),
            extraction_type="schema",
            instruction=f"""Extract search results from DuckDuckGo search page.

            For each result extract:
            - title: Result title/heading
            - snippet: Description text
            - url: Target URL

            Focus on results from consultant.ru and garant.ru.

            Query: "{query}"
            Return top {max_results} results.
            """,
            input_format="markdown",
            apply_chunking=False
        )

        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(
                url=search_url,
                delay_before_return_html=2.0,
                extraction_strategy=extraction_strategy,
                screenshot=False
            )

            if not result.success:
                logger.warning(f"[DUCKDUCKGO] Crawl failed: {result.error_message}")
                return []

            if result.extracted_content:
                import json
                try:
                    extracted = json.loads(result.extracted_content)

                    if isinstance(extracted, dict) and 'results' in extracted:
                        items = extracted['results']
                    elif isinstance(extracted, list):
                        items = extracted
                    else:
                        items = [extracted]

                    results = []
                    for item in items[:max_results]:
                        if isinstance(item, dict):
                            results.append({
                                'title': item.get('title', ''),
                                'snippet': item.get('snippet', ''),
                                'url': item.get('url', ''),
                                'source': 'duckduckgo',
                                'extraction_method': 'llm'
                            })

                    logger.info(f"[DUCKDUCKGO] Found {len(results)} results")
                    return results

                except Exception as e:
                    logger.error(f"[DUCKDUCKGO] Extraction failed: {e}")
                    return []

            return []

    except Exception as e:
        logger.error(f"[DUCKDUCKGO] Search error: {e}")
        return []


async def simple_web_search(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    Универсальная функция web search (UPDATED 2025-10-05)
    Пробует Google (лучше для определений), fallback на DuckDuckGo

    Args:
        query: Поисковый запрос
        max_results: Максимум результатов

    Returns:
        Список результатов с title, snippet, url
    """
    logger.info(f"[WEB SEARCH] Starting search for: '{query}'")
    
    if GOOGLE_AVAILABLE:
        try:
            logger.info("[WEB SEARCH] Trying Google...")
            results = await asyncio.wait_for(
                async_search_google(query, max_results=max_results),
                timeout=12,
            )
            if results and len(results) > 0:
                logger.info(f"[WEB SEARCH] Google found {len(results)} results")
                return results
            else:
                logger.info("[WEB SEARCH] Google returned no results, trying DuckDuckGo...")
        except Exception as e:
            logger.warning(f"[WEB SEARCH] Google error: {e}, trying DuckDuckGo...")
    
    if not DUCKDUCKGO_AVAILABLE:
        logger.error("[WEB SEARCH] No search engines available")
        return []

    try:
        logger.info("[WEB SEARCH] Using DuckDuckGo...")
        results = await asyncio.wait_for(
            async_search_duckduckgo(query, max_results=max_results),
            timeout=12,
        )
        if results:
            logger.info(f"[WEB SEARCH] DuckDuckGo found {len(results)} results")
            return results
        else:
            logger.warning("[WEB SEARCH] No results found")
            return []
    except asyncio.TimeoutError:
        logger.warning("[WEB SEARCH] DuckDuckGo timeout")
        return []
    except Exception as e:
        logger.error(f"[WEB SEARCH] DuckDuckGo error: {e}")
        return []


# Test
if __name__ == "__main__":
    async def test():
        query = "что такое плата концедента"
        print(f"Searching: {query}\n")

        results = await simple_web_search(query, max_results=3)

        print(f"\nFound {len(results)} results:\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r.get('title', 'NO TITLE')}")
            print(f" URL: {r.get('url', 'N/A')}")
            print(f" Snippet: {r.get('snippet', 'NO SNIPPET')[:150]}...")
            print()

    asyncio.run(test())
