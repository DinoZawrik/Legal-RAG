#!/usr/bin/env python3
"""
Graph-based search tools for Neo4j
Tools for searching definitions and relationships in legal knowledge graph
"""

import logging
import os
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """Singleton Neo4j connection"""
    _instance = None
    _driver = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_driver(self):
        """Get or create Neo4j driver"""
        if self._driver is None:
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "change_me_in_env")
            self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
            logger.info(f"Connected to Neo4j at {uri}")
        return self._driver

    async def close(self):
        """Close driver"""
        if self._driver:
            await self._driver.close()
            self._driver = None


async def search_definition_in_graph(term: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search for a definition in Neo4j graph
    
    Args:
        term: The term to search for
        max_results: Maximum number of results
        
    Returns:
        List of definition results with text, law, article
    """
    conn = Neo4jConnection()
    driver = await conn.get_driver()
    
    results = []
    
    async with driver.session() as session:
        # Try multiple search strategies
        # 1. Exact match (full term)
        # 2. Individual word matching (for multi-word terms)
        
        # Split term into words for flexible matching
        words = [w.strip() for w in term.lower().split() if len(w.strip()) > 2]
        
        # Build query with word-based matching
        query = """
        MATCH (d:Definition)
        WHERE toLower(d.term) CONTAINS toLower($term)
           OR toLower(d.term_original) CONTAINS toLower($term)
           OR toLower(d.full_term) CONTAINS toLower($term)
        """
        
        # Add word-based conditions for multi-word terms
        if len(words) > 1:
            for i, word in enumerate(words):
                query += f"""
           OR toLower(d.term) CONTAINS toLower($word{i})
           OR toLower(d.term_original) CONTAINS toLower($word{i})
           OR toLower(d.full_term) CONTAINS toLower($word{i})
        """
        
        query += """
        OPTIONAL MATCH (d)-[rel]->(a:Article)
        WHERE type(rel) = 'DEFINED_IN'
        RETURN d.term as term,
               d.term_original as term_original,
               d.full_term as full_term,
               d.definition_text as definition_text,
               d.law as law,
               d.article as article,
               a.article_number as article_number
        LIMIT $max_results
        """
        
        # Build parameters
        params = {"term": term, "max_results": max_results}
        if len(words) > 1:
            for i, word in enumerate(words):
                params[f"word{i}"] = word
        
        result = await session.run(query, **params)
        
        async for record in result:
            results.append({
                "term": record["term"],
                "term_original": record["term_original"],
                "full_term": record.get("full_term"),
                "definition_text": record["definition_text"],
                "law": record["law"] or "unknown",
                "article": record["article"] or record["article_number"] or "",
                "source_type": "graph_definition"
            })
    
    return results


@tool
async def graph_definition_lookup(term: str) -> str:
    """
    Search for legal term definition in Neo4j knowledge graph.
    Use this when looking for "Что такое X?" or definitions.
    
    Args:
        term: The legal term to search for (e.g., "плата концедента")
        
    Returns:
        JSON string with definition results
    """
    import json
    
    logger.info(f"[GRAPH] Searching for definition: '{term}'")
    
    try:
        results = await search_definition_in_graph(term, max_results=5)
        
        if not results:
            logger.info(f"[GRAPH] No definition found for '{term}'")
            return json.dumps({
                "found": False,
                "message": f"Определение термина '{term}' не найдено в графе"
            }, ensure_ascii=False)
        
        logger.info(f"[GRAPH] Found {len(results)} definition(s) for '{term}'")
        
        # Format results
        formatted_results = []
        for r in results:
            formatted_results.append({
                "term": r["term_original"],
                "definition": r["definition_text"],
                "source": f"{r['law']} - Статья {r['article']}" if r['article'] else r['law'],
                "type": "graph_definition"
            })
        
        return json.dumps({
            "found": True,
            "count": len(formatted_results),
            "results": formatted_results
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"[GRAPH] Error searching for '{term}': {e}")
        return json.dumps({
            "found": False,
            "error": str(e)
        }, ensure_ascii=False)
