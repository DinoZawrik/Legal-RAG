#!/usr/bin/env python3
"""
Smart Search - Search Engine (Context7 validated).

This module contains the main search engine with scoring and matching logic
with proper type hints as per Context7 best practices.

Author: LegalRAG Development Team
License: MIT
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from .query_analyzer import QueryAnalyzer
from .result_ranker import ResultRanker
from .types import (
    QueryAnalysis,
    QueryType,
    SearchMode,
    SearchResult,
    SmartSearchResults,
)

logger = logging.getLogger(__name__)


class UniversalSmartSearch:
    """
    Universal intelligent search system.

    Combines:
    - Semantic query analysis
    - Entity-aware search
    - Context-based ranking
    - Adaptive filtering
    """

    def __init__(self) -> None:
        """Initialize smart search engine."""
        from ..universal_legal_ner import get_universal_legal_ner

        ner_engine = get_universal_legal_ner()
        self.query_analyzer = QueryAnalyzer(ner_engine)
        self.result_ranker = ResultRanker()

        self.scoring_weights = {
            'semantic_similarity': 0.35,
            'entity_match': 0.25,
            'context_relevance': 0.15,
            'document_authority': 0.10,
            'recency': 0.08,
            'chunk_priority': 0.07
        }

        logger.info("[UniversalSmartSearch] Initialized")

    def search(
        self,
        query: str,
        source_chunks: List[Dict[str, Any]],
        max_results: int = 10,
        search_mode: SearchMode = SearchMode.BALANCED
    ) -> SmartSearchResults:
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
        logger.info(f"[SmartSearch] Query: '{query[:50]}...' in {len(source_chunks)} chunks")

        try:
            query_analysis = self.query_analyzer.analyze_query(query, search_mode)
            logger.info(f"[QueryType] {query_analysis.query_type.value}")

            search_results = self._perform_multi_modal_search(query_analysis, source_chunks)
            ranked_results = self.result_ranker.rank_results(query_analysis, search_results)
            filtered_results = self.result_ranker.filter_by_quality(ranked_results, search_mode)
            final_results = filtered_results[:max_results]

            suggestions = self.result_ranker.generate_search_suggestions(
                query_analysis, final_results
            )
            search_stats = self.result_ranker.collect_search_statistics(
                query_analysis, search_results, final_results
            )

            logger.info(f"[SearchComplete] {len(final_results)} results found")

            return SmartSearchResults(
                query_analysis=query_analysis,
                results=final_results,
                total_found=len(search_results),
                search_stats=search_stats,
                performance_metrics=self.result_ranker.calculate_performance_metrics(
                    search_results, final_results
                ),
                search_suggestions=suggestions
            )

        except Exception as e:
            logger.error(f"[SearchError] {e}")
            return self._create_empty_results(query, search_mode, str(e))

    def _perform_multi_modal_search(
        self,
        query_analysis: QueryAnalysis,
        source_chunks: List[Dict[str, Any]]
    ) -> List[SearchResult]:
        """Perform multi-modal search."""
        all_results = []

        for chunk in source_chunks:
            result = self._search_in_chunk(query_analysis, chunk)
            if result:
                all_results.append(result)

        return all_results

    def _search_in_chunk(
        self,
        query_analysis: QueryAnalysis,
        chunk: Dict[str, Any]
    ) -> Optional[SearchResult]:
        """Search in specific chunk."""
        content = chunk.get('content', '') or chunk.get('text', '')
        metadata = chunk.get('metadata', {})

        if not content:
            return None

        semantic_score = self._calculate_semantic_score(query_analysis, content)
        entity_match_score = self._calculate_entity_match_score(
            query_analysis, content, metadata
        )
        context_relevance_score = self._calculate_context_relevance_score(
            query_analysis, content
        )
        authority_score = self._calculate_authority_score(metadata)
        recency_score = self._calculate_recency_score(metadata)

        boosted_scores = self._apply_boost_factors(
            query_analysis,
            {
                'semantic': semantic_score,
                'entity_match': entity_match_score,
                'context_relevance': context_relevance_score,
                'authority': authority_score,
                'recency': recency_score
            },
            metadata
        )

        final_score = (
            boosted_scores['semantic'] * self.scoring_weights['semantic_similarity'] +
            boosted_scores['entity_match'] * self.scoring_weights['entity_match'] +
            boosted_scores['context_relevance'] * self.scoring_weights['context_relevance'] +
            boosted_scores['authority'] * self.scoring_weights['document_authority'] +
            boosted_scores['recency'] * self.scoring_weights['recency']
        )

        chunk_priority = metadata.get('chunk_priority', 'normal')
        priority_boost = {
            'critical': 1.3,
            'high': 1.2,
            'normal': 1.0,
            'low': 0.9
        }.get(chunk_priority, 1.0)
        final_score *= priority_boost

        relevance_explanation = self._generate_relevance_explanation(
            query_analysis, content, metadata, boosted_scores
        )
        matched_entities = self._find_matched_entities(query_analysis, content)
        matched_keywords = self._find_matched_keywords(query_analysis, content)

        return SearchResult(
            content=content,
            metadata=metadata,
            semantic_score=boosted_scores['semantic'],
            entity_match_score=boosted_scores['entity_match'],
            context_relevance_score=boosted_scores['context_relevance'],
            authority_score=boosted_scores['authority'],
            recency_score=boosted_scores['recency'],
            final_score=final_score,
            relevance_explanation=relevance_explanation,
            matched_entities=matched_entities,
            matched_keywords=matched_keywords,
            chunk_priority=chunk_priority,
            search_criticality=metadata.get('search_criticality', 0.5),
            source_document=metadata.get('document_title', 'Unknown document')
        )

    def _calculate_semantic_score(
        self,
        query_analysis: QueryAnalysis,
        content: str
    ) -> float:
        """Calculate semantic similarity."""
        query_words = set(query_analysis.keywords)
        content_words = set(re.findall(r'\b\w+\b', content.lower()))

        if not query_words or not content_words:
            return 0.0

        intersection = len(query_words & content_words)
        union = len(query_words | content_words)

        jaccard_similarity = intersection / union if union > 0 else 0.0

        phrase_bonus = 0.0
        query_text = query_analysis.original_query.lower()
        if len(query_text) > 10:
            query_phrases = re.findall(r'\b\w+\s+\w+\s+\w+\b', query_text)
            for phrase in query_phrases:
                if phrase in content.lower():
                    phrase_bonus += 0.2

        return min(jaccard_similarity + phrase_bonus, 1.0)

    def _calculate_entity_match_score(
        self,
        query_analysis: QueryAnalysis,
        content: str,
        metadata: Dict[str, Any]
    ) -> float:
        """Calculate entity match score."""
        score = 0.0

        if query_analysis.numerical_values:
            for value in query_analysis.numerical_values:
                if value.lower() in content.lower():
                    score += 0.5

        if query_analysis.document_references:
            for ref in query_analysis.document_references:
                if ref.lower() in content.lower():
                    score += 0.3

        query_has_numerical = len(query_analysis.entities.numerical_constraints) > 0
        chunk_has_numerical = metadata.get('has_numerical_constraints', False)

        if query_has_numerical and chunk_has_numerical:
            score += 0.4

        query_has_definitions = len(query_analysis.entities.definitions) > 0
        chunk_has_definitions = metadata.get('has_definitions', False)

        if query_has_definitions and chunk_has_definitions:
            score += 0.3

        return min(score, 1.0)

    def _calculate_context_relevance_score(
        self,
        query_analysis: QueryAnalysis,
        content: str
    ) -> float:
        """Calculate context relevance score."""
        score = 0.0

        type_indicators = {
            QueryType.NUMERICAL_QUERY: [
                'процент', 'размер', 'сумма', 'срок', 'ограничение'
            ],
            QueryType.DEFINITION_QUERY: [
                'понимается', 'означает', 'является', 'представляет'
            ],
            QueryType.PROCEDURE_QUERY: [
                'порядок', 'процедура', 'этапы', 'последовательность'
            ],
            QueryType.AUTHORITY_QUERY: [
                'обязан', 'вправе', 'может', 'права', 'обязанности'
            ],
            QueryType.CONDITION_QUERY: [
                'в случае', 'при условии', 'если', 'когда'
            ]
        }

        indicators = type_indicators.get(query_analysis.query_type, [])
        content_lower = content.lower()

        for indicator in indicators:
            if indicator in content_lower:
                score += 0.2

        if len(query_analysis.keywords) > 1:
            for i, word1 in enumerate(query_analysis.keywords[:-1]):
                for word2 in query_analysis.keywords[i+1:]:
                    if word1 in content_lower and word2 in content_lower:
                        pos1 = content_lower.find(word1)
                        pos2 = content_lower.find(word2)
                        distance = abs(pos1 - pos2)

                        if distance < 100:
                            score += 0.15

        return min(score, 1.0)

    def _calculate_authority_score(self, metadata: Dict[str, Any]) -> float:
        """Calculate source authority score."""
        score = 0.5

        doc_type = metadata.get('document_type', '').lower()
        if 'федеральный закон' in doc_type:
            score += 0.3
        elif 'кодекс' in doc_type:
            score += 0.25
        elif 'постановление' in doc_type:
            score += 0.15

        if metadata.get('article_number'):
            score += 0.1

        criticality = metadata.get('search_criticality', 0.5)
        score += criticality * 0.1

        return min(score, 1.0)

    def _calculate_recency_score(self, metadata: Dict[str, Any]) -> float:
        """Calculate recency score."""
        score = 0.5

        if metadata.get('adoption_date'):
            score += 0.2

        if metadata.get('processed_at'):
            score += 0.1

        return min(score, 1.0)

    def _apply_boost_factors(
        self,
        query_analysis: QueryAnalysis,
        scores: Dict[str, float],
        metadata: Dict[str, Any]
    ) -> Dict[str, float]:
        """Apply boost factors to scores."""
        boosted_scores = scores.copy()

        for boost_key, boost_factor in query_analysis.boost_factors.items():
            if boost_key == 'exact_numerical_match':
                if self._has_exact_numerical_match(query_analysis, metadata):
                    boosted_scores['entity_match'] *= boost_factor
            elif boost_key == 'numerical_constraints':
                if metadata.get('has_numerical_constraints', False):
                    boosted_scores['entity_match'] *= boost_factor
            elif boost_key == 'definitions':
                if metadata.get('has_definitions', False):
                    boosted_scores['entity_match'] *= boost_factor
            elif boost_key.startswith('chunk_priority_'):
                priority_level = boost_key.replace('chunk_priority_', '')
                if metadata.get('chunk_priority', 'normal') == priority_level:
                    boosted_scores['context_relevance'] *= boost_factor

        return boosted_scores

    def _has_exact_numerical_match(
        self,
        query_analysis: QueryAnalysis,
        metadata: Dict[str, Any]
    ) -> bool:
        """Check for exact numerical match."""
        if not query_analysis.numerical_values:
            return False

        numerical_constraints = metadata.get('numerical_constraints', [])
        for constraint in numerical_constraints:
            constraint_value = constraint.get('value', '')
            constraint_unit = constraint.get('unit', '')

            for query_value in query_analysis.numerical_values:
                if constraint_value in query_value or query_value in f"{constraint_value} {constraint_unit}":
                    return True

        return False

    def _generate_relevance_explanation(
        self,
        query_analysis: QueryAnalysis,
        content: str,
        metadata: Dict[str, Any],
        scores: Dict[str, float]
    ) -> List[str]:
        """Generate relevance explanations."""
        explanations = []

        if scores['semantic'] > 0.7:
            explanations.append("High semantic similarity with query")

        if scores['entity_match'] > 0.5:
            explanations.append("Found matching legal entities")

        if metadata.get('has_numerical_constraints') and query_analysis.query_type == QueryType.NUMERICAL_QUERY:
            explanations.append("Contains numerical constraints")

        if metadata.get('chunk_priority') == 'critical':
            explanations.append("Critical document fragment")

        article = metadata.get('article_number')
        if article:
            explanations.append(f"From article {article}")

        return explanations

    def _find_matched_entities(
        self,
        query_analysis: QueryAnalysis,
        content: str
    ) -> List[str]:
        """Find matched entities."""
        matched = []

        for value in query_analysis.numerical_values:
            if value.lower() in content.lower():
                matched.append(f"Numerical value: {value}")

        for ref in query_analysis.document_references:
            if ref.lower() in content.lower():
                matched.append(f"Reference: {ref}")

        return matched

    def _find_matched_keywords(
        self,
        query_analysis: QueryAnalysis,
        content: str
    ) -> List[str]:
        """Find matched keywords."""
        content_lower = content.lower()
        matched = [kw for kw in query_analysis.keywords if kw in content_lower]
        return matched[:5]

    def _create_empty_results(
        self,
        query: str,
        search_mode: SearchMode,
        error: str
    ) -> SmartSearchResults:
        """Create empty results on error."""
        from ..universal_legal_ner import UniversalLegalEntities

        return SmartSearchResults(
            query_analysis=QueryAnalysis(
                original_query=query,
                query_type=QueryType.GENERAL_QUERY,
                search_mode=search_mode,
                entities=UniversalLegalEntities(),
                keywords=[],
                numerical_values=[],
                document_references=[],
                intent_confidence=0.0,
                complexity_score=0.0,
                ambiguity_score=1.0
            ),
            results=[],
            total_found=0,
            search_stats={'error': error},
            performance_metrics={'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0},
            search_suggestions=['Search error occurred, please try again']
        )


_universal_smart_search: Optional[UniversalSmartSearch] = None


def get_universal_smart_search() -> UniversalSmartSearch:
    """Get global UniversalSmartSearch instance."""
    global _universal_smart_search
    if _universal_smart_search is None:
        _universal_smart_search = UniversalSmartSearch()
    return _universal_smart_search


__all__ = ["UniversalSmartSearch", "get_universal_smart_search"]
