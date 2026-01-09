"""
Search module - Backward compatibility exports.

Re-exports all search components for seamless migration from
core.universal_smart_search to core.search.

This module provides the UniversalSmartSearch facade that combines
QueryAnalyzer and SearchEngine for a unified interface.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, TYPE_CHECKING

# Import query analyzer components
from .query_analyzer import (
    QueryType,
    SearchMode,
    QueryAnalysis,
    QueryAnalyzer,
    LegalEntities
)

# Import search engine components
from .search_engine import (
    SearchResult,
    SmartSearchResults,
    SearchEngine
)

if TYPE_CHECKING:
    from ..universal_legal_ner import UniversalLegalNER

logger = logging.getLogger(__name__)


class UniversalSmartSearch:
    """
    Universal intelligent search system (facade).

    Combines:
    - Semantic query analysis
    - Entity-aware search
    - Context ranking
    - Adaptive filtering

    This class maintains backward compatibility with the original
    monolithic implementation.
    """

    def __init__(self) -> None:
        """Initialize Universal Smart Search."""
        from ..universal_legal_ner import get_universal_legal_ner

        self.ner_engine = get_universal_legal_ner()
        self.query_analyzer = QueryAnalyzer(self.ner_engine)
        self.search_engine = SearchEngine()

        # Expose internal attributes for backward compatibility
        self.query_patterns = self.query_analyzer.query_patterns
        self.scoring_weights = self.search_engine.scoring_weights
        self.score_thresholds = self.search_engine.score_thresholds

        logger.info("[PASS] Universal Smart Search initialized")

    def search(self,
               query: str,
               source_chunks: List[Dict[str, Any]],
               max_results: int = 10,
               search_mode: SearchMode = SearchMode.BALANCED) -> SmartSearchResults:
        """
        Main smart search method.

        Args:
            query: Search query
            source_chunks: List of chunks to search
            max_results: Maximum number of results
            search_mode: Search mode

        Returns:
            Smart search results with analysis
        """
        logger.info(f"Smart search: '{query[:50]}...' in {len(source_chunks)} chunks")

        try:
            # 1. Analyze query
            query_analysis = self.query_analyzer.analyze_query(query, search_mode)
            logger.info(f"Query type: {query_analysis.query_type.value}")

            # 2. Perform search
            results = self.search_engine.perform_search(query_analysis, source_chunks, max_results)

            logger.info(f"[PASS] Search completed: {len(results.results)} results found")
            return results

        except Exception as e:
            logger.error(f"[FAIL] Smart search error: {e}")
            return self._create_empty_results(query, search_mode, str(e))

    def _analyze_query(self, query: str, search_mode: SearchMode) -> QueryAnalysis:
        """Analyze user query (backward compatibility method)."""
        return self.query_analyzer.analyze_query(query, search_mode)

    def _create_empty_results(self, query: str, search_mode: SearchMode, error: str) -> SmartSearchResults:
        """Create empty results in case of error."""
        query_analysis = QueryAnalysis(
            original_query=query,
            query_type=QueryType.GENERAL_QUERY,
            search_mode=search_mode,
            entities=LegalEntities(),
            keywords=[],
            numerical_values=[],
            document_references=[],
            intent_confidence=0.0,
            complexity_score=0.0,
            ambiguity_score=1.0
        )

        return SmartSearchResults(
            query_analysis=query_analysis,
            results=[],
            total_found=0,
            search_stats={'error': error},
            performance_metrics={'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0},
            search_suggestions=['Search error occurred, please try again']
        )


# Global instance for use in other modules
_universal_smart_search: UniversalSmartSearch | None = None


def get_universal_smart_search() -> UniversalSmartSearch:
    """Get global instance of Universal Smart Search."""
    global _universal_smart_search
    if _universal_smart_search is None:
        _universal_smart_search = UniversalSmartSearch()
    return _universal_smart_search


# Export all components
__all__ = [
    # Enums
    "QueryType",
    "SearchMode",

    # Data classes
    "QueryAnalysis",
    "SearchResult",
    "SmartSearchResults",
    "LegalEntities",

    # Core classes
    "QueryAnalyzer",
    "SearchEngine",
    "UniversalSmartSearch",

    # Factory function
    "get_universal_smart_search",
]
