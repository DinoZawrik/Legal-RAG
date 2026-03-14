#!/usr/bin/env python3
"""
Simple Google Search (через requests, без Crawl4AI)
Идеален для поиска определений - Google показывает их в featured snippets
"""

import logging
import re
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def search_google_simple(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Простой Google search через HTML (без JavaScript)
    
    Args:
        query: Поисковый запрос
        max_results: Максимум результатов
        
    Returns:
        Список результатов с title, snippet, url
    """
    try:
        # Enhance query для юридических поисков
        enhanced_query = query
        
        # Google search URL
        import urllib.parse
        encoded_query = urllib.parse.quote(enhanced_query)
        url = f"https://www.google.com/search?q={encoded_query}&hl=ru&num={max_results * 2}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        }
        
        logger.info(f"[GOOGLE] Searching: {enhanced_query}")
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        
        # 1. Try to extract featured snippet first (best for definitions)
        featured = soup.find('div', class_=re.compile(r'kp-wholepage|kno-rdesc'))
        if featured and len(results) < max_results:
            snippet_text = featured.get_text(strip=True, separator=' ')
            if len(snippet_text) > 50: # Valid snippet
                results.append({
                    'title': 'Определение (Google Featured Snippet)',
                    'snippet': snippet_text[:500], # First 500 chars
                    'url': 'https://www.google.com/search?q=' + encoded_query,
                    'source': 'google_featured'
                })
                logger.info("[GOOGLE] Found featured snippet")
        
        # 2. Extract organic results - FLEXIBLE APPROACH
        # Try multiple selectors since Google changes structure frequently
        
        # Method 1: Find all <a> tags with /url?q= pattern
        all_links = soup.find_all('a', href=re.compile(r'/url\?q='))
        
        for link in all_links:
            if len(results) >= max_results:
                break
            
            href = link.get('href', '')
            
            # Extract actual URL from Google redirect
            if '/url?q=' in href:
                url_match = re.search(r'/url\?q=([^&]+)', href)
                if url_match:
                    import urllib.parse
                    href = urllib.parse.unquote(url_match.group(1))
            
            if not href.startswith('http'):
                continue
            
            # Skip Google's own links
            if 'google.com' in href:
                continue
            
            # Extract title (look for <h3> near this link)
            parent = link.find_parent('div')
            if not parent:
                continue
            
            title_tag = parent.find('h3')
            title = title_tag.get_text(strip=True) if title_tag else href.split('/')[2]
            
            # Extract snippet (any text in parent div)
            snippet = parent.get_text(strip=True, separator=' ')
            # Clean up snippet
            snippet = re.sub(r'\s+', ' ', snippet) # Multiple spaces to one
            snippet = snippet.replace(title, '', 1) # Remove title from snippet
            
            if len(snippet) < 20: # Too short
                continue
            
            # Filter: prefer consultant.ru, garant.ru, gov.ru
            priority = any(domain in href.lower() for domain in ['consultant.ru', 'garant.ru', '.gov.ru'])
            
            if priority or len(results) < 3: # Always take first 3 results
                results.append({
                    'title': title[:200],
                    'snippet': snippet[:400],
                    'url': href,
                    'source': 'google'
                })
                logger.info(f"[GOOGLE] Found: {title[:50]}... from {href[:50]}...")
        
        logger.info(f"[GOOGLE] Found {len(results)} results")
        return results
        
    except Exception as e:
        logger.error(f"[GOOGLE] Search error: {e}")
        return []


async def async_search_google(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Async wrapper for Google search
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, search_google_simple, query, max_results)


if __name__ == "__main__":
    # Test
    from core.logging_config import configure_logging

    configure_logging()
    results = search_google_simple("что такое плата концедента", max_results=3)
    
    print(f"\nНайдено {len(results)} результатов:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']}")
        print(f" {r['snippet'][:150]}...")
        print(f" {r['url']}\n")
