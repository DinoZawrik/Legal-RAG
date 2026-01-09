#!/usr/bin/env python3
"""
🦆 DuckDuckGo Search (без Crawl4AI)
Использует requests + BeautifulSoup для надежного веб-поиска
"""

import logging
import re
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def search_duckduckgo_simple(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Простой DuckDuckGo search через HTML (без JavaScript)
    
    Args:
        query: Поисковый запрос
        max_results: Максимум результатов
        
    Returns:
        Список результатов с title, snippet, url
    """
    try:
        enhanced_query = query
        
        # DuckDuckGo HTML (работает без JS)
        url = "https://html.duckduckgo.com/html/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        data = {
            'q': enhanced_query,
            'kl': 'ru-ru'  # Russian results
        }
        
        logger.info(f"[DDG] Searching: {enhanced_query}")
        
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        result_divs = soup.find_all('div', class_='result', limit=max_results * 2)
        
        for div in result_divs:
            if len(results) >= max_results:
                break
                
            # Extract title
            title_tag = div.find('a', class_='result__a')
            if not title_tag:
                continue
                
            title = title_tag.get_text(strip=True)
            href = title_tag.get('href', '')
            
            # Extract snippet
            snippet_tag = div.find('a', class_='result__snippet')
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            
            # Clean URL (DuckDuckGo wraps URLs)
            if href.startswith('//duckduckgo.com/l/?'):
                # Extract real URL from redirect
                url_match = re.search(r'uddg=([^&]+)', href)
                if url_match:
                    import urllib.parse
                    href = urllib.parse.unquote(url_match.group(1))
            
            results.append({
                'title': title,
                'snippet': snippet,
                'url': href,
                'source': 'duckduckgo'
            })
        
        logger.info(f"[DDG] ✅ Found {len(results)} results")
        return results
        
    except Exception as e:
        logger.error(f"[DDG] Search error: {e}")
        return []


async def async_search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Async wrapper for DuckDuckGo search
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, search_duckduckgo_simple, query, max_results)


if __name__ == "__main__":
    # Test
    from core.logging_config import configure_logging

    configure_logging()
    results = search_duckduckgo_simple("что такое плата концедента", max_results=3)
    
    print(f"\nНайдено {len(results)} результатов:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']}")
        print(f"   {r['snippet'][:100]}...")
        print(f"   {r['url']}\n")
