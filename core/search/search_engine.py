"""
Search engine core module (Context7 validated).

This module contains the main search execution logic, scoring algorithms,
and result ranking for the Universal Smart Search system. Uses async patterns
and proper type hints as per Context7 best practices.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .query_analyzer import QueryAnalysis, QueryType, SearchMode

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Search result with extended metadata."""
    content: str
    metadata: Dict[str, Any]

    # Scoring information
    semantic_score: float
    entity_match_score: float
    context_relevance_score: float
    authority_score: float
    recency_score: float
    final_score: float

    # Relevance explanation
    relevance_explanation: List[str]
    matched_entities: List[str]
    matched_keywords: List[str]

    # Additional information
    chunk_priority: str
    search_criticality: float
    source_document: Optional[str] = None


@dataclass
class SmartSearchResults:
    """Collection of smart search results."""
    query_analysis: QueryAnalysis
    results: List[SearchResult]
    total_found: int

    # Search statistics
    search_stats: Dict[str, Any]
    performance_metrics: Dict[str, float]

    # Recommendations
    search_suggestions: List[str] = field(default_factory=list)
    alternative_queries: List[str] = field(default_factory=list)


class SearchEngine:
    """
    Core search engine for legal document search.

    Executes multi-modal search with semantic matching, entity matching,
    and context relevance scoring.
    """

    def __init__(self) -> None:
        """Initialize search engine."""
        # Weights for various scoring factors
        self.scoring_weights = {
            'semantic_similarity': 0.35,
            'entity_match': 0.25,
            'context_relevance': 0.15,
            'document_authority': 0.10,
            'recency': 0.08,
            'chunk_priority': 0.07
        }

        # Score thresholds for filtering
        from .query_analyzer import SearchMode
        self.score_thresholds = {
            SearchMode.PRECISION: 0.7,
            SearchMode.BALANCED: 0.5,
            SearchMode.RECALL: 0.3,
            SearchMode.NUMERICAL_FOCUS: 0.6
        }

        logger.info("Search Engine initialized")

    def perform_search(self,
                      query_analysis: QueryAnalysis,
                      source_chunks: List[Dict[str, Any]],
                      max_results: int = 10) -> SmartSearchResults:
        """
        Perform smart search.

        Args:
            query_analysis: Analyzed query
            source_chunks: List of chunks to search
            max_results: Maximum number of results

        Returns:
            Smart search results with analysis
        """
        logger.info(f"Executing search in {len(source_chunks)} chunks")

        try:
            # 1. Perform multi-modal search
            search_results = self._perform_multi_modal_search(query_analysis, source_chunks)

            # 2. Rank results
            ranked_results = self._rank_results(query_analysis, search_results)

            # 3. Filter by quality
            filtered_results = self._filter_by_quality(ranked_results, query_analysis.search_mode)

            # 4. Limit number of results
            final_results = filtered_results[:max_results]

            # 5. Generate recommendations
            suggestions = self._generate_search_suggestions(query_analysis, final_results)

            # 6. Collect statistics
            search_stats = self._collect_search_statistics(query_analysis, search_results, final_results)

            logger.info(f"Search completed: {len(final_results)} results found")

            return SmartSearchResults(
                query_analysis=query_analysis,
                results=final_results,
                total_found=len(search_results),
                search_stats=search_stats,
                performance_metrics=self._calculate_performance_metrics(search_results, final_results),
                search_suggestions=suggestions
            )

        except Exception as e:
            logger.error(f"Search error: {e}")
            return self._create_empty_results(query_analysis, str(e))

    def _perform_multi_modal_search(self,
                                   query_analysis: QueryAnalysis,
                                   source_chunks: List[Dict[str, Any]]) -> List[SearchResult]:
        """Perform multi-level search."""
        all_results = []

        for chunk in source_chunks:
            result = self._search_in_chunk(query_analysis, chunk)
            if result:
                all_results.append(result)

        return all_results

    def _search_in_chunk(self, query_analysis: QueryAnalysis, chunk: Dict[str, Any]) -> Optional[SearchResult]:
        """Perform search in specific chunk."""
        content = chunk.get('content', '') or chunk.get('text', '')
        metadata = chunk.get('metadata', {})

        if not content:
            return None

        # Base scores
        semantic_score = self._calculate_semantic_score(query_analysis, content)
        entity_match_score = self._calculate_entity_match_score(query_analysis, content, metadata)
        context_relevance_score = self._calculate_context_relevance_score(query_analysis, content)
        authority_score = self._calculate_authority_score(metadata)
        recency_score = self._calculate_recency_score(metadata)

        # Apply boost factors
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

        # Calculate final score
        final_score = (
            boosted_scores['semantic'] * self.scoring_weights['semantic_similarity'] +
            boosted_scores['entity_match'] * self.scoring_weights['entity_match'] +
            boosted_scores['context_relevance'] * self.scoring_weights['context_relevance'] +
            boosted_scores['authority'] * self.scoring_weights['document_authority'] +
            boosted_scores['recency'] * self.scoring_weights['recency']
        )

        # Additional boost for chunk priority
        chunk_priority = metadata.get('chunk_priority', 'normal')
        priority_boost = {'critical': 1.3, 'high': 1.2, 'normal': 1.0, 'low': 0.9}.get(chunk_priority, 1.0)
        final_score *= priority_boost

        # Generate relevance explanations
        relevance_explanation = self._generate_relevance_explanation(query_analysis, content, metadata, boosted_scores)
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

    def _calculate_semantic_score(self, query_analysis: QueryAnalysis, content: str) -> float:
        """Calculate semantic similarity."""
        query_words = set(query_analysis.keywords)
        content_words = set(re.findall(r'\b\w+\b', content.lower()))

        if not query_words or not content_words:
            return 0.0

        intersection = len(query_words & content_words)
        union = len(query_words | content_words)

        jaccard_similarity = intersection / union if union > 0 else 0.0

        # Bonus for exact phrases
        phrase_bonus = 0.0
        query_text = query_analysis.original_query.lower()
        if len(query_text) > 10:
            # Search for phrases of 3+ words
            query_phrases = re.findall(r'\b\w+\s+\w+\s+\w+\b', query_text)
            for phrase in query_phrases:
                if phrase in content.lower():
                    phrase_bonus += 0.2

        return min(jaccard_similarity + phrase_bonus, 1.0)

    def _calculate_entity_match_score(self,
                                    query_analysis: QueryAnalysis,
                                    content: str,
                                    metadata: Dict[str, Any]) -> float:
        """Calculate entity match score."""
        score = 0.0

        # Numerical matches (high priority)
        if query_analysis.numerical_values:
            for value in query_analysis.numerical_values:
                if value.lower() in content.lower():
                    score += 0.5  # High weight for exact numerical matches

        # Document references
        if query_analysis.document_references:
            for ref in query_analysis.document_references:
                if ref.lower() in content.lower():
                    score += 0.3

        # Entity type matching from metadata
        query_has_numerical = len(query_analysis.entities.numerical_constraints) > 0
        chunk_has_numerical = metadata.get('has_numerical_constraints', False)

        if query_has_numerical and chunk_has_numerical:
            score += 0.4

        query_has_definitions = len(query_analysis.entities.definitions) > 0
        chunk_has_definitions = metadata.get('has_definitions', False)

        if query_has_definitions and chunk_has_definitions:
            score += 0.3

        return min(score, 1.0)

    def _calculate_context_relevance_score(self, query_analysis: QueryAnalysis, content: str) -> float:
        """Calculate context relevance score."""
        from .query_analyzer import QueryType

        score = 0.0

        # Query type matching
        type_indicators = {
            QueryType.NUMERICAL_QUERY: ['процент', 'размер', 'сумма', 'срок', 'ограничение'],
            QueryType.DEFINITION_QUERY: ['понимается', 'означает', 'является', 'представляет'],
            QueryType.PROCEDURE_QUERY: ['порядок', 'процедура', 'этапы', 'последовательность'],
            QueryType.AUTHORITY_QUERY: ['обязан', 'вправе', 'может', 'права', 'обязанности'],
            QueryType.CONDITION_QUERY: ['в случае', 'при условии', 'если', 'когда']
        }

        indicators = type_indicators.get(query_analysis.query_type, [])
        content_lower = content.lower()

        for indicator in indicators:
            if indicator in content_lower:
                score += 0.2

        # Contextual proximity of keywords
        if len(query_analysis.keywords) > 1:
            for i, word1 in enumerate(query_analysis.keywords[:-1]):
                for word2 in query_analysis.keywords[i+1:]:
                    if word1 in content_lower and word2 in content_lower:
                        # Check word proximity
                        pos1 = content_lower.find(word1)
                        pos2 = content_lower.find(word2)
                        distance = abs(pos1 - pos2)

                        if distance < 100:  # Words are close to each other
                            score += 0.15

        return min(score, 1.0)

    def _calculate_authority_score(self, metadata: Dict[str, Any]) -> float:
        """Calculate source authority score."""
        score = 0.5  # Base level

        # Document type
        doc_type = metadata.get('document_type', '').lower()
        if 'федеральный закон' in doc_type:
            score += 0.3
        elif 'кодекс' in doc_type:
            score += 0.25
        elif 'постановление' in doc_type:
            score += 0.15

        # Article number presence
        if metadata.get('article_number'):
            score += 0.1

        # Chunk criticality
        criticality = metadata.get('search_criticality', 0.5)
        score += criticality * 0.1

        return min(score, 1.0)

    def _calculate_recency_score(self, metadata: Dict[str, Any]) -> float:
        """Calculate recency score."""
        # Simple implementation - can be improved with real dates
        score = 0.5

        # Adoption date
        adoption_date = metadata.get('adoption_date')
        if adoption_date:
            # Conditional logic: newer documents get higher score
            score += 0.2

        # Processing date
        processed_at = metadata.get('processed_at')
        if processed_at:
            score += 0.1

        return min(score, 1.0)

    def _apply_boost_factors(self,
                           query_analysis: QueryAnalysis,
                           scores: Dict[str, float],
                           metadata: Dict[str, Any]) -> Dict[str, float]:
        """Apply boost factors to scores."""
        boosted_scores = scores.copy()

        for boost_key, boost_factor in query_analysis.boost_factors.items():
            if boost_key == 'exact_numerical_match':
                # Check exact numerical matches
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

    def _has_exact_numerical_match(self, query_analysis: QueryAnalysis, metadata: Dict[str, Any]) -> bool:
        """Check for exact numerical match."""
        if not query_analysis.numerical_values:
            return False

        # Check numerical constraints metadata
        numerical_constraints = metadata.get('numerical_constraints', [])
        for constraint in numerical_constraints:
            constraint_value = constraint.get('value', '')
            constraint_unit = constraint.get('unit', '')

            for query_value in query_analysis.numerical_values:
                if constraint_value in query_value or query_value in f"{constraint_value} {constraint_unit}":
                    return True

        return False

    def _generate_relevance_explanation(self,
                                      query_analysis: QueryAnalysis,
                                      content: str,
                                      metadata: Dict[str, Any],
                                      scores: Dict[str, float]) -> List[str]:
        """Generate relevance explanations."""
        from .query_analyzer import QueryType

        explanations = []

        if scores['semantic'] > 0.7:
            explanations.append("High semantic similarity with query")

        if scores['entity_match'] > 0.5:
            explanations.append("Found matching legal entities")

        if metadata.get('has_numerical_constraints') and query_analysis.query_type == QueryType.NUMERICAL_QUERY:
            explanations.append("Contains numerical constraints")

        if metadata.get('chunk_priority') == 'critical':
            explanations.append("Critically important document fragment")

        article = metadata.get('article_number')
        if article:
            explanations.append(f"From article {article}")

        return explanations

    def _find_matched_entities(self, query_analysis: QueryAnalysis, content: str) -> List[str]:
        """Find matched entities."""
        matched = []

        for value in query_analysis.numerical_values:
            if value.lower() in content.lower():
                matched.append(f"Numerical value: {value}")

        for ref in query_analysis.document_references:
            if ref.lower() in content.lower():
                matched.append(f"Reference: {ref}")

        return matched

    def _find_matched_keywords(self, query_analysis: QueryAnalysis, content: str) -> List[str]:
        """Find matched keywords."""
        content_lower = content.lower()
        matched = [kw for kw in query_analysis.keywords if kw in content_lower]
        return matched[:5]  # Limit quantity

    def _rank_results(self, query_analysis: QueryAnalysis, results: List[SearchResult]) -> List[SearchResult]:
        """Rank search results."""
        from .query_analyzer import QueryType

        # Sort by final score
        ranked = sorted(results, key=lambda x: x.final_score, reverse=True)

        # Additional ranking logic for specific queries
        if query_analysis.query_type == QueryType.NUMERICAL_QUERY:
            # Priority to results with numerical data
            ranked.sort(key=lambda x: (x.entity_match_score, x.final_score), reverse=True)

        elif query_analysis.query_type == QueryType.DEFINITION_QUERY:
            # Priority to results with definitions
            ranked.sort(key=lambda x: (
                x.metadata.get('has_definitions', False),
                x.final_score
            ), reverse=True)

        return ranked

    def _filter_by_quality(self, results: List[SearchResult], search_mode: Any) -> List[SearchResult]:
        """Filter results by quality."""
        from .query_analyzer import SearchMode

        threshold = self.score_thresholds.get(search_mode, 0.5)
        filtered = [r for r in results if r.final_score >= threshold]

        # Additional filtering for precision mode
        if search_mode == SearchMode.PRECISION:
            # Keep only results with high entity match
            filtered = [r for r in filtered if r.entity_match_score >= 0.4]

        elif search_mode == SearchMode.NUMERICAL_FOCUS:
            # Filtering for numerical queries
            filtered = [r for r in filtered if
                       r.entity_match_score >= 0.3 or
                       r.metadata.get('has_numerical_constraints', False)]

        return filtered

    def _generate_search_suggestions(self,
                                   query_analysis: QueryAnalysis,
                                   results: List[SearchResult]) -> List[str]:
        """Generate search improvement suggestions."""
        from .query_analyzer import QueryType

        suggestions = []

        if len(results) == 0:
            suggestions.append("Try using more general terms")
            suggestions.append("Check spelling of keywords")

            if query_analysis.query_type == QueryType.NUMERICAL_QUERY:
                suggestions.append("Specify exact numerical values from documents")

        elif len(results) > 20:
            suggestions.append("Refine query for more relevant results")

            if query_analysis.ambiguity_score > 0.7:
                suggestions.append("Query is too general - add specific terms")

        # Suggestions based on query type
        if query_analysis.query_type == QueryType.GENERAL_QUERY:
            suggestions.append("Specify what interests you: procedure, constraints, definitions")

        return suggestions

    def _collect_search_statistics(self,
                                  query_analysis: QueryAnalysis,
                                  all_results: List[SearchResult],
                                  final_results: List[SearchResult]) -> Dict[str, Any]:
        """Collect search statistics."""
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

    def _calculate_performance_metrics(self,
                                     all_results: List[SearchResult],
                                     final_results: List[SearchResult]) -> Dict[str, float]:
        """Calculate performance metrics."""
        if not all_results:
            return {'precision': 0.0, 'recall': 1.0, 'f1_score': 0.0}

        # Simple metrics based on scores
        high_quality_results = [r for r in all_results if r.final_score >= 0.8]
        precision = len([r for r in final_results if r.final_score >= 0.8]) / len(final_results) if final_results else 0
        recall = len(high_quality_results) / len(all_results) if all_results else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        return {
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score
        }

    def _create_empty_results(self, query_analysis: QueryAnalysis, error: str) -> SmartSearchResults:
        """Create empty results in case of error."""
        return SmartSearchResults(
            query_analysis=query_analysis,
            results=[],
            total_found=0,
            search_stats={'error': error},
            performance_metrics={'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0},
            search_suggestions=['Search error occurred, please try again']
        )
