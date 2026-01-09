#!/usr/bin/env python3
"""
Smart Search - Result Ranker (Context7 validated).

This module handles result ranking, filtering, and suggestion generation
with proper type hints as per Context7 best practices.

Author: LegalRAG Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .types import QueryAnalysis, QueryType, SearchMode, SearchResult

logger = logging.getLogger(__name__)


class ResultRanker:
    """Ranks and filters search results."""

    def __init__(self) -> None:
        """Initialize result ranker."""
        self.score_thresholds = {
            SearchMode.PRECISION: 0.7,
            SearchMode.BALANCED: 0.5,
            SearchMode.RECALL: 0.3,
            SearchMode.NUMERICAL_FOCUS: 0.6
        }

    def rank_results(
        self,
        query_analysis: QueryAnalysis,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Rank search results.

        Args:
            query_analysis: Query analysis result
            results: List of search results to rank

        Returns:
            Ranked list of search results
        """
        ranked = sorted(results, key=lambda x: x.final_score, reverse=True)

        if query_analysis.query_type == QueryType.NUMERICAL_QUERY:
            ranked.sort(
                key=lambda x: (x.entity_match_score, x.final_score),
                reverse=True
            )
        elif query_analysis.query_type == QueryType.DEFINITION_QUERY:
            ranked.sort(
                key=lambda x: (
                    x.metadata.get('has_definitions', False),
                    x.final_score
                ),
                reverse=True
            )

        return ranked

    def filter_by_quality(
        self,
        results: List[SearchResult],
        search_mode: SearchMode
    ) -> List[SearchResult]:
        """
        Filter results by quality.

        Args:
            results: List of search results
            search_mode: Search mode determining threshold

        Returns:
            Filtered list of search results
        """
        threshold = self.score_thresholds.get(search_mode, 0.5)
        filtered = [r for r in results if r.final_score >= threshold]

        if search_mode == SearchMode.PRECISION:
            filtered = [r for r in filtered if r.entity_match_score >= 0.4]
        elif search_mode == SearchMode.NUMERICAL_FOCUS:
            filtered = [
                r for r in filtered
                if r.entity_match_score >= 0.3 or
                r.metadata.get('has_numerical_constraints', False)
            ]

        return filtered

    def generate_search_suggestions(
        self,
        query_analysis: QueryAnalysis,
        results: List[SearchResult]
    ) -> List[str]:
        """
        Generate search suggestions.

        Args:
            query_analysis: Query analysis result
            results: List of search results

        Returns:
            List of search suggestions
        """
        suggestions = []

        if len(results) == 0:
            suggestions.append("Попробуйте использовать более общие термины")
            suggestions.append("Проверьте правописание ключевых слов")

            if query_analysis.query_type == QueryType.NUMERICAL_QUERY:
                suggestions.append("Укажите точные числовые значения из документов")

        elif len(results) > 20:
            suggestions.append("Уточните запрос для получения более релевантных результатов")

            if query_analysis.ambiguity_score > 0.7:
                suggestions.append("Запрос слишком общий - добавьте специфические термины")

        if query_analysis.query_type == QueryType.GENERAL_QUERY:
            suggestions.append(
                "Уточните, что именно вас интересует: процедура, ограничения, определения"
            )

        return suggestions

    def collect_search_statistics(
        self,
        query_analysis: QueryAnalysis,
        all_results: List[SearchResult],
        final_results: List[SearchResult]
    ) -> Dict[str, Any]:
        """
        Collect search statistics.

        Args:
            query_analysis: Query analysis result
            all_results: All search results before filtering
            final_results: Final filtered results

        Returns:
            Dictionary with search statistics
        """
        return {
            'query_type': query_analysis.query_type.value,
            'search_mode': query_analysis.search_mode.value,
            'total_candidates': len(all_results),
            'filtered_results': len(final_results),
            'filter_ratio': len(final_results) / len(all_results) if all_results else 0,
            'avg_score': sum(r.final_score for r in final_results) / len(final_results) if final_results else 0,
            'keywords_used': len(query_analysis.keywords),
            'numerical_values_found': len(query_analysis.numerical_values),
            'intent_confidence': query_analysis.intent_confidence,
            'complexity_score': query_analysis.complexity_score
        }

    def calculate_performance_metrics(
        self,
        all_results: List[SearchResult],
        final_results: List[SearchResult]
    ) -> Dict[str, float]:
        """
        Calculate performance metrics.

        Args:
            all_results: All search results before filtering
            final_results: Final filtered results

        Returns:
            Dictionary with performance metrics
        """
        if not all_results:
            return {'precision': 0.0, 'recall': 1.0, 'f1_score': 0.0}

        high_quality_results = [r for r in all_results if r.final_score >= 0.8]
        precision = (
            len([r for r in final_results if r.final_score >= 0.8]) / len(final_results)
            if final_results else 0
        )
        recall = len(high_quality_results) / len(all_results) if all_results else 0
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0 else 0
        )

        return {
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score
        }


__all__ = ["ResultRanker"]
