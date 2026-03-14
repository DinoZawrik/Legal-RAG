#!/usr/bin/env python3
"""
Web Search Tools for Legal Document Search
Fallback search in external legal databases (КонсультантПлюс, Гарант)
Uses Crawl4AI for LLM-friendly web scraping
"""

import os
import sys
import logging
import asyncio
import re
import json
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool

# Load environment variables (critical for GEMINI_API_KEY)
from dotenv import load_dotenv
load_dotenv()

# Fix Windows console encoding for Crawl4AI rich output
if sys.platform == 'win32':
    try:
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        sys.stdout.reconfigure(encoding='utf-8', errors='ignore')
        sys.stderr.reconfigure(encoding='utf-8', errors='ignore')
    except Exception:
        pass

logger = logging.getLogger(__name__)

# Allowed domains for web crawling (SSRF protection)
_ALLOWED_CRAWL_DOMAINS = {
    "consultant.ru",
    "www.consultant.ru",
    "garant.ru",
    "www.garant.ru",
    "publication.pravo.gov.ru",
    "pravo.gov.ru",
    "base.garant.ru",
}


def _is_url_allowed(url: str) -> bool:
    """Check that a URL belongs to an allowed domain."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        return any(hostname == d or hostname.endswith("." + d) for d in _ALLOWED_CRAWL_DOMAINS)
    except Exception:
        return False

# Import Crawl4AI
try:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
    from pydantic import BaseModel, Field
    CRAWL4AI_AVAILABLE = True
except ImportError:
    logger.warning("Crawl4AI not available - install with: pip install crawl4ai")
    CRAWL4AI_AVAILABLE = False

# Pydantic model for structured extraction
class LegalSearchResult(BaseModel):
    """Single search result"""
    title: str = Field(description="Document or article title")
    snippet: str = Field(description="Short description or excerpt from the document")
    url: str = Field(description="Full URL to the document")
    law_number: str = Field(default="", description="Law number if mentioned")
    relevance: str = Field(default="medium", description="Relevance: high/medium/low")


class LegalSearchResults(BaseModel):
    """List of legal search results for LLM extraction"""
    results: list[LegalSearchResult] = Field(description="List of search results")


class WebSearchRateLimiter:
    """Rate limiter for web searches to avoid overload"""

    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.last_request_time = 0
        self.min_interval = 60.0 / requests_per_minute

    async def wait_if_needed(self):
        """Wait if necessary to respect rate limit"""
        import time
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            logger.info(f"[RATE LIMIT] Waiting {wait_time:.2f}s...")
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()


class WebSearchCache:
    """Redis-based cache for web search results"""

    def __init__(self, ttl_hours: int = 24):
        self.ttl_hours = ttl_hours
        self.ttl_seconds = ttl_hours * 3600
        self.redis_client = None

    async def get_redis(self):
        """Get or create Redis client"""
        if self.redis_client is None:
            try:
                import redis.asyncio as redis
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                self.redis_client = await redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info("[CACHE] Redis client connected")
            except Exception as e:
                logger.warning(f"[CACHE] Redis unavailable: {e}")
                self.redis_client = None
        return self.redis_client

    def _make_cache_key(self, source: str, query: str, max_results: int) -> str:
        """Create cache key from search parameters"""
        import hashlib
        query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()[:8]
        return f"web_search:{source}:{query_hash}:{max_results}"

    async def get(self, source: str, query: str, max_results: int) -> Optional[List[Dict[str, Any]]]:
        """Get cached results"""
        redis = await self.get_redis()
        if not redis:
            return None

        try:
            key = self._make_cache_key(source, query, max_results)
            cached = await redis.get(key)

            if cached:
                import json
                results = json.loads(cached)
                logger.info(f"[CACHE HIT] {source} - {query} ({len(results)} results)")
                return results
        except Exception as e:
            logger.warning(f"[CACHE] Get failed: {e}")

        return None

    async def set(self, source: str, query: str, max_results: int, results: List[Dict[str, Any]]):
        """Cache results"""
        redis = await self.get_redis()
        if not redis:
            return

        try:
            import json
            key = self._make_cache_key(source, query, max_results)
            value = json.dumps(results, ensure_ascii=False)
            await redis.setex(key, self.ttl_seconds, value)
            logger.info(f"[CACHE SET] {source} - {query} (TTL: {self.ttl_hours}h)")
        except Exception as e:
            logger.warning(f"[CACHE] Set failed: {e}")


def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0):
    """
    Decorator for retry logic with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds (doubles with each retry)
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            delay = initial_delay

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        # Last attempt failed
                        logger.error(f"[RETRY] Failed after {max_retries} attempts: {e}")
                        raise

                    # Wait with exponential backoff
                    logger.warning(f"[RETRY] Attempt {attempt + 1}/{max_retries} failed: {e}")
                    logger.info(f"[RETRY] Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay *= 2 # Exponential backoff

        return wrapper
    return decorator


# Global instances
_rate_limiter = WebSearchRateLimiter(requests_per_minute=10)
_search_cache = WebSearchCache(ttl_hours=24)


@retry_with_backoff(max_retries=3, initial_delay=2.0)
async def _crawl_consultant_plus(search_url: str, query: str, max_results: int, extraction_strategy) -> List[Dict[str, Any]]:
    """Internal function with retry logic for КонсультантПлюс crawling"""
    if not _is_url_allowed(search_url):
        logger.warning(f"[SSRF] Blocked crawl to non-whitelisted URL: {search_url}")
        return []
    async with AsyncWebCrawler(verbose=False) as crawler:
        # Import CrawlerRunConfig
        from crawl4ai import CrawlerRunConfig, CacheMode

        # Create crawler config with extraction strategy
        crawl_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            cache_mode=CacheMode.BYPASS, # Bypass cache for fresh results
            delay_before_return_html=3.0 # Wait for JS
        )

        # Full page crawl with config
        result = await crawler.arun(
            url=search_url,
            config=crawl_config
        )

        if not result.success:
            raise Exception(f"Crawl failed: {result.error_message}")

        # Try LLM extraction first
        if extraction_strategy and result.extracted_content:
            try:
                logger.info(f"[CONSULTANT+] LLM extraction returned: {len(result.extracted_content)} chars")

                import json
                extracted = json.loads(result.extracted_content)
                results = []

                # Handle Pydantic schema format: {"results": [...]}
                if isinstance(extracted, dict) and 'results' in extracted:
                    items = extracted['results']
                    logger.info(f"[CONSULTANT+] Found Pydantic format with {len(items)} results")
                # Handle direct list format
                elif isinstance(extracted, list):
                    items = extracted
                    logger.info(f"[CONSULTANT+] Found list format with {len(items)} items")
                # Handle single object
                else:
                    items = [extracted]
                    logger.info(f"[CONSULTANT+] Found single object format")

                for item in items[:max_results]:
                    if isinstance(item, dict):
                        results.append({
                            'title': item.get('title', ''),
                            'snippet': item.get('snippet', ''),
                            'url': item.get('url', search_url),
                            'law_number': item.get('law_number', ''),
                            'relevance': item.get('relevance', 'medium'),
                            'source': 'consultant_plus',
                            'extraction_method': 'llm' # Mark as LLM extracted
                        })

                if results:
                    logger.info(f"[CONSULTANT+] LLM extracted {len(results)} results")
                    return results
                else:
                    logger.warning("[CONSULTANT+] LLM extraction returned 0 results")
            except Exception as e:
                logger.warning(f"[CONSULTANT+] LLM extraction parse failed: {e}, using regex fallback")
        elif extraction_strategy:
            logger.warning("[CONSULTANT+] LLM strategy set but no extracted_content returned")

        # Fallback: Regex parsing from markdown
        results = []
        markdown = result.markdown

        # Extract links that look like search results
        link_pattern = r'\[(.*?)\]\((https?://www\.consultant\.ru/document/.*?)\)'
        matches = re.findall(link_pattern, markdown)

        for title, url in matches[:max_results]:
            # Find snippet (next few lines after the link)
            title_pos = markdown.find(f'[{title}]')
            if title_pos != -1:
                snippet_start = title_pos + len(f'[{title}]({url})')
                snippet_end = markdown.find('\n\n', snippet_start)
                snippet = markdown[snippet_start:snippet_end].strip() if snippet_end != -1 else ""
            else:
                snippet = ""

            results.append({
                'title': title.strip(),
                'snippet': snippet[:300], # Limit snippet length
                'url': url,
                'source': 'consultant_plus',
                'extraction_method': 'regex' # Mark as regex extracted
            })

        logger.info(f"[CONSULTANT+] Regex extracted {len(results)} results (LLM fallback)")
        return results


async def search_consultant_plus(query: str, max_results: int = 3, use_llm: bool = True) -> List[Dict[str, Any]]:
    """
    Search КонсультантПлюс using Crawl4AI with LLM extraction

    Args:
        query: Search query
        max_results: Maximum number of results
        use_llm: Use LLM extraction strategy (default True)

    Returns:
        List of search results
    """
    # Check cache first
    cached_results = await _search_cache.get("consultant_plus", query, max_results)
    if cached_results is not None:
        return cached_results

    await _rate_limiter.wait_if_needed()

    logger.info(f"[CONSULTANT+] Searching for: '{query}' (LLM={'ON' if use_llm else 'OFF'})")

    if not CRAWL4AI_AVAILABLE:
        logger.error("[CONSULTANT+] Crawl4AI not installed")
        return []

    try:
        # КонсультантПлюс НЕКОММЕРЧЕСКАЯ ВЕРСИЯ (бесплатный доступ к законам)
        # Используем прямые ссылки на законы для лучшей доступности
        import urllib.parse
        encoded_query = urllib.parse.quote(query)

        search_url = f"https://www.consultant.ru/search/?q={encoded_query}"

        # LLM extraction strategy
        extraction_strategy = None
        if use_llm:
            try:
                from core.api_key_manager import get_key_manager
                gemini_key = get_key_manager().get_next_key()
                if gemini_key:
                    from crawl4ai import LLMConfig

                    # Use Pydantic model_json_schema() with Gemini 2.5 Flash Lite (15 RPM)
                    # Для extraction достаточно lite версии
                    extraction_strategy = LLMExtractionStrategy(
                        llm_config=LLMConfig(
                            provider="gemini/gemini-2.5-flash-lite-preview-09-2025",
                            api_token=gemini_key
                        ),
                        schema=LegalSearchResults.model_json_schema(),
                        extraction_type="schema",
                        instruction=f"""You are reading the full text of a Russian federal law from КонсультантПлюс.

                        Task: Find the definition or answer to the query in this law text.

                        Query: "{query}"

                        Instructions:
                        1. Search for the term or concept from the query in the law text
                        2. Find the article/section that DEFINES this term (look for "понимается", "означает", "признается")
                        3. Extract the FULL definition with article number
                        4. Include surrounding context if helpful

                        Return format:
                        - title: "Статья X. [Article title]"
                        - snippet: [Full definition text with context]
                        - law_number: [Extract from document if present]
                        - article: [Article number, e.g., "10.1"]
                        - url: [Keep the URL provided]

                        Return up to {max_results} most relevant definitions/sections from this law.
                        Focus on DEFINITIONS and legal explanations, not examples or consultations.
                        """,
                        input_format="markdown",
                        apply_chunking=False
                    )
                    logger.info("[CONSULTANT+] Using LLM extraction strategy")
                else:
                    logger.warning("[CONSULTANT+] GEMINI_API_KEY not found, falling back to regex")
            except Exception as e:
                import traceback
                logger.error(f"[CONSULTANT+] LLM strategy init failed: {e}")
                logger.error(f"[CONSULTANT+] Full traceback:\n{traceback.format_exc()}")
                logger.warning("[CONSULTANT+] Using regex fallback")

        # Use retry-enabled crawl function
        results = await _crawl_consultant_plus(search_url, query, max_results, extraction_strategy)

        # Cache results
        if results:
            await _search_cache.set("consultant_plus", query, max_results, results)

        return results

    except Exception as e:
        logger.error(f"[CONSULTANT+] Search error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def search_garant(query: str, max_results: int = 3, use_llm: bool = True) -> List[Dict[str, Any]]:
    """
    Search Гарант using Crawl4AI with LLM extraction

    Args:
        query: Search query
        max_results: Maximum number of results
        use_llm: Use LLM extraction strategy (default True)

    Returns:
        List of search results
    """
    # Check cache first
    cached_results = await _search_cache.get("garant", query, max_results)
    if cached_results is not None:
        return cached_results

    await _rate_limiter.wait_if_needed()

    logger.info(f"[GARANT] Searching for: '{query}' (LLM={'ON' if use_llm else 'OFF'})")

    if not CRAWL4AI_AVAILABLE:
        logger.error("[GARANT] Crawl4AI not installed")
        return []

    try:
        # Гарант search URL with proper encoding
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.garant.ru/search/?text={encoded_query}&sort=0"

        # LLM extraction strategy
        extraction_strategy = None
        if use_llm:
            try:
                from core.api_key_manager import get_key_manager
                gemini_key = get_key_manager().get_next_key()
                if gemini_key:
                    from crawl4ai import LLMConfig

                    # Use Pydantic model_json_schema() with Gemini 2.5 Flash Lite (15 RPM)
                    # Для extraction достаточно lite версии
                    extraction_strategy = LLMExtractionStrategy(
                        llm_config=LLMConfig(
                            provider="gemini/gemini-2.5-flash-lite-preview-09-2025",
                            api_token=gemini_key
                        ),
                        schema=LegalSearchResults.model_json_schema(),
                        extraction_type="schema",
                        instruction=f"""Extract search results from Гарант page.
                        Look for:
                        - Document titles (laws, codes, articles)
                        - Short descriptions or snippets
                        - URLs to full documents
                        - Law numbers if present

                        Only extract actual search RESULTS, not navigation links or ads.
                        Return up to {max_results} most relevant results for query: "{query}"
                        """,
                        input_format="markdown",
                        apply_chunking=False
                    )
                    logger.info("[GARANT] Using LLM extraction strategy")
                else:
                    logger.warning("[GARANT] GEMINI_API_KEY not found, falling back to regex")
            except Exception as e:
                logger.warning(f"[GARANT] LLM strategy init failed: {e}, using regex fallback")

        async with AsyncWebCrawler(verbose=False) as crawler:
            # Full page crawl with optional LLM extraction
            result = await crawler.arun(
                url=search_url,
                delay_before_return_html=3.0, # Wait for JS to load results
                wait_for="css:.result,.b-result", # Wait for result elements
                extraction_strategy=extraction_strategy,
                screenshot=False
            )

            if not result.success:
                logger.warning(f"[GARANT] Failed to crawl: {result.error_message}")
                return []

            # Try LLM extraction first
            if use_llm and result.extracted_content:
                try:
                    import json
                    extracted = json.loads(result.extracted_content)
                    results = []

                    items = extracted if isinstance(extracted, list) else [extracted]

                    for item in items[:max_results]:
                        if isinstance(item, dict):
                            results.append({
                                'title': item.get('title', ''),
                                'snippet': item.get('snippet', ''),
                                'url': item.get('url', search_url),
                                'law_number': item.get('law_number', ''),
                                'relevance': item.get('relevance', 'medium'),
                                'source': 'garant'
                            })

                    if results:
                        logger.info(f"[GARANT] LLM extracted {len(results)} results")
                        return results
                except Exception as e:
                    logger.warning(f"[GARANT] LLM extraction parse failed: {e}, using regex fallback")

            # Fallback: Regex parsing from markdown
            results = []
            markdown = result.markdown

            # Extract links that look like search results
            link_pattern = r'\[(.*?)\]\((https?://(?:www\.)?garant\.ru/(?:products|ia/document)/.*?)\)'
            matches = re.findall(link_pattern, markdown)

            for title, url in matches[:max_results]:
                # Find snippet (next few lines after the link)
                title_pos = markdown.find(f'[{title}]')
                if title_pos != -1:
                    snippet_start = title_pos + len(f'[{title}]({url})')
                    snippet_end = markdown.find('\n\n', snippet_start)
                    snippet = markdown[snippet_start:snippet_end].strip() if snippet_end != -1 else ""
                else:
                    snippet = ""

                results.append({
                    'title': title.strip(),
                    'snippet': snippet[:300], # Limit snippet length
                    'url': url,
                    'source': 'garant'
                })

            logger.info(f"[GARANT] Regex extracted {len(results)} results")

            # Cache results
            if results:
                await _search_cache.set("garant", query, max_results, results)

            return results

    except Exception as e:
        logger.error(f"[GARANT] Search error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def search_legal_web(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Combined web search - UPDATED to use simple Google/DuckDuckGo search

    Fallback order:
    1. Google search (with focus on consultant.ru, garant.ru)
    2. DuckDuckGo if Google fails

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of search results with LLM extraction
    """
    logger.info(f"[WEB SEARCH] Starting simple web search for: '{query}'")

    try:
        # Import simple web search
        from tools.simple_web_search import simple_web_search

        # Use simple Google/DuckDuckGo search
        results = await simple_web_search(query, max_results=max_results)

        if results:
            logger.info(f"[WEB SEARCH] Found {len(results)} results via web")
            return results

        logger.warning("[WEB SEARCH] No results from web search")
        return []

    except Exception as e:
        logger.error(f"[WEB SEARCH] Error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def search_legal_web_old(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    OLD VERSION: Combined web search across КонсультантПлюс and Гарант
    Kept for reference, not used anymore
    """
    logger.info(f"[WEB SEARCH OLD] Starting search for: '{query}'")

    # Search both sources in parallel
    consultant_task = search_consultant_plus(query, max_results=max_results)
    garant_task = search_garant(query, max_results=max_results)

    consultant_results, garant_results = await asyncio.gather(
        consultant_task, garant_task, return_exceptions=True
    )

    # Handle exceptions
    if isinstance(consultant_results, Exception):
        logger.error(f"[WEB SEARCH] Consultant+ error: {consultant_results}")
        consultant_results = []

    if isinstance(garant_results, Exception):
        logger.error(f"[WEB SEARCH] Garant error: {garant_results}")
        garant_results = []

    # Combine results
    all_results = []

    for result in consultant_results:
        result['source'] = 'consultant_plus'
        all_results.append(result)

    for result in garant_results:
        result['source'] = 'garant'
        all_results.append(result)
    
    logger.info(f"[WEB SEARCH] Found {len(all_results)} total results")
    
    return all_results


@tool
async def web_legal_search(query: str) -> str:
    """
    Search for legal information on external websites (КонсультантПлюс, Гарант).
    Use this as last resort when internal databases don't have the answer.
    
    Args:
        query: Search query (e.g., "что такое плата концедента")
        
    Returns:
        JSON string with search results
    """
    
    logger.info(f"[WEB TOOL] Searching for: '{query}'")
    
    try:
        results = await search_legal_web(query, max_results=5)
        
        if not results:
            logger.warning(f"[WEB TOOL] No results found for '{query}'")
            return json.dumps({
                "found": False,
                "message": f"Информация по запросу '{query}' не найдена в внешних источниках"
            }, ensure_ascii=False)
        
        logger.info(f"[WEB TOOL] Found {len(results)} results")
        
        # Format results
        formatted_results = []
        for r in results:
            formatted_results.append({
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "url": r.get("url", ""),
                "source": r.get("source", "unknown")
            })
        
        return json.dumps({
            "found": True,
            "count": len(formatted_results),
            "results": formatted_results
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"[WEB TOOL] Error: {e}")
        return json.dumps({
            "found": False,
            "error": str(e)
        }, ensure_ascii=False)
