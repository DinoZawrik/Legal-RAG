#!/usr/bin/env python3
"""
Smart Search - Query Analyzer (Context7 validated).

This module handles query analysis, classification, and entity extraction
with proper type hints as per Context7 best practices.

Author: LegalRAG Development Team
License: MIT
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from .types import QueryAnalysis, QueryType, SearchMode

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Analyzes and classifies user queries."""

    def __init__(self, ner_engine: Any) -> None:
        """
        Initialize query analyzer.

        Args:
            ner_engine: Universal Legal NER engine instance
        """
        self.ner_engine = ner_engine
        self.query_patterns = self._initialize_query_patterns()

    def _initialize_query_patterns(self) -> Dict[QueryType, List[str]]:
        """Initialize query classification patterns."""
        return {
            QueryType.NUMERICAL_QUERY: [
                r'(?:сколько|какой размер|какая сумма|процент|ограничение)',
                r'(?:не может превышать|не менее|не более|составляет)',
                r'(?:\d+\s*%|\d+\s*процент|\d+\s*лет|\d+\s*года)',
                r'(?:максимальный|минимальный|предельный)\s+(?:размер|срок|сумма)'
            ],
            QueryType.DEFINITION_QUERY: [
                r'(?:что такое|что означает|определение|понятие)',
                r'(?:что понимается под|как определяется)',
                r'(?:дайте определение|объясните термин)'
            ],
            QueryType.PROCEDURE_QUERY: [
                r'(?:как|каким образом|в каком порядке)',
                r'(?:процедура|порядок|последовательность|алгоритм)',
                r'(?:этапы|шаги|стадии)',
                r'(?:необходимо|нужно|требуется)\s+(?:сделать|выполнить)'
            ],
            QueryType.AUTHORITY_QUERY: [
                r'(?:кто|может ли|вправе ли|обязан ли)',
                r'(?:права|обязанности|полномочия|ответственность)',
                r'(?:имеет право|не вправе|обязан|должен)'
            ],
            QueryType.REFERENCE_QUERY: [
                r'(?:статья|пункт|часть|подпункт)\s+\d+',
                r'(?:федеральный закон|кодекс|постановление)',
                r'(?:115-фз|224-фз|\d+-фз)',
                r'(?:ссылка на|см\.|согласно)'
            ],
            QueryType.CONDITION_QUERY: [
                r'(?:в случае|при условии|если|когда)',
                r'(?:что происходит|что делать|как поступить)',
                r'(?:последствия|результат|итог)'
            ],
            QueryType.COMPARISON_QUERY: [
                r'(?:разница|отличие|сравнение|в чем разница)',
                r'(?:чем отличается|что общего)',
                r'(?:лучше|хуже|предпочтительнее)',
                r'(?:альтернатива|вариант|выбор)'
            ]
        }

    def analyze_query(self, query: str, search_mode: SearchMode) -> QueryAnalysis:
        """
        Analyze user query.

        Args:
            query: User query string
            search_mode: Search mode to use

        Returns:
            QueryAnalysis with extracted information
        """
        entities = self.ner_engine.extract_entities(query)
        query_type = self._classify_query_type(query)
        keywords = self._extract_keywords(query)
        numerical_values = self._extract_numerical_values(query)
        document_references = self._extract_document_references(query)

        intent_confidence = self._calculate_intent_confidence(query, query_type)
        complexity_score = self._calculate_complexity_score(query, entities)
        ambiguity_score = self._calculate_ambiguity_score(query, keywords)

        suggested_filters = self._generate_filters(query_type, entities)
        boost_factors = self._generate_boost_factors(query_type, entities, numerical_values)

        return QueryAnalysis(
            original_query=query,
            query_type=query_type,
            search_mode=search_mode,
            entities=entities,
            keywords=keywords,
            numerical_values=numerical_values,
            document_references=document_references,
            intent_confidence=intent_confidence,
            complexity_score=complexity_score,
            ambiguity_score=ambiguity_score,
            suggested_filters=suggested_filters,
            boost_factors=boost_factors
        )

    def _classify_query_type(self, query: str) -> QueryType:
        """Classify query type."""
        query_lower = query.lower()
        scores = {}

        for query_type, patterns in self.query_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, query_lower))
                score += matches

            if score > 0:
                scores[query_type] = score

        if scores:
            return max(scores.keys(), key=lambda x: scores[x])
        else:
            return QueryType.GENERAL_QUERY

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from query."""
        stop_words = {
            'что', 'как', 'где', 'когда', 'почему', 'который',
            'какой', 'можно', 'нужно', 'должен', 'может'
        }

        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]

        legal_terms = {
            'концессионер', 'концедент', 'концессия', 'соглашение', 'партнер',
            'грант', 'финансирование', 'расходы', 'обязательства', 'права',
            'статья', 'закон', 'кодекс', 'процедура', 'порядок'
        }

        prioritized_keywords = []
        for word in keywords:
            if word in legal_terms:
                prioritized_keywords.insert(0, word)
            else:
                prioritized_keywords.append(word)

        return prioritized_keywords[:10]

    def _extract_numerical_values(self, query: str) -> List[str]:
        """Extract numerical values from query."""
        patterns = [
            r'\d+(?:[.,]\d+)?\s*%',
            r'\d+(?:[.,]\d+)?\s*процент[а-я]*',
            r'\d+\s*лет',
            r'\d+\s*года?',
            r'\d+(?:[.,]\d+)?\s*(?:млн|млрд|тыс)',
            r'\d+(?:[.,]\d+)?'
        ]

        values = []
        for pattern in patterns:
            matches = re.findall(pattern, query.lower())
            values.extend(matches)

        return list(set(values))

    def _extract_document_references(self, query: str) -> List[str]:
        """Extract document references from query."""
        patterns = [
            r'статья\s+\d+(?:\.\d+)?',
            r'пункт\s+\d+',
            r'часть\s+\d+',
            r'\d+-фз',
            r'федеральный\s+закон',
            r'кодекс'
        ]

        references = []
        for pattern in patterns:
            matches = re.findall(pattern, query.lower())
            references.extend(matches)

        return references

    def _calculate_intent_confidence(self, query: str, query_type: QueryType) -> float:
        """Calculate intent confidence score."""
        if query_type == QueryType.GENERAL_QUERY:
            return 0.5

        patterns = self.query_patterns.get(query_type, [])
        matches = sum(len(re.findall(pattern, query.lower())) for pattern in patterns)

        confidence = min(matches / (len(query.split()) / 3), 1.0)
        return max(confidence, 0.3)

    def _calculate_complexity_score(self, query: str, entities: Any) -> float:
        """Calculate query complexity score."""
        score = 0.0

        score += min(len(query.split()) / 20, 0.3)

        entity_count = len(entities.get_all_entities())
        score += min(entity_count / 10, 0.3)

        conditional_patterns = ['если', 'в случае', 'при условии', 'когда']
        if any(pattern in query.lower() for pattern in conditional_patterns):
            score += 0.2

        if re.search(r'\d+', query):
            score += 0.2

        return min(score, 1.0)

    def _calculate_ambiguity_score(self, query: str, keywords: List[str]) -> float:
        """Calculate query ambiguity score."""
        score = 0.0

        common_words = {'может', 'нужно', 'должен', 'право', 'обязан'}
        common_count = sum(1 for word in keywords if word in common_words)
        score += min(common_count / len(keywords) if keywords else 0, 0.4)

        specific_terms = {'статья', 'пункт', 'процедура', 'размер', 'срок'}
        if not any(term in query.lower() for term in specific_terms):
            score += 0.3

        if ('что' in query.lower() or 'как' in query.lower()) and len(keywords) < 3:
            score += 0.3

        return min(score, 1.0)

    def _generate_filters(self, query_type: QueryType, entities: Any) -> Dict[str, Any]:
        """Generate search filters."""
        filters = {}

        if query_type == QueryType.NUMERICAL_QUERY:
            filters['has_numerical_constraints'] = True
        elif query_type == QueryType.DEFINITION_QUERY:
            filters['has_definitions'] = True
        elif query_type == QueryType.PROCEDURE_QUERY:
            filters['has_procedure_steps'] = True
        elif query_type == QueryType.AUTHORITY_QUERY:
            filters['has_authority_modals'] = True

        if entities.numerical_constraints:
            filters['numerical_priority'] = True

        if entities.definitions:
            filters['definition_priority'] = True

        return filters

    def _generate_boost_factors(
        self,
        query_type: QueryType,
        entities: Any,
        numerical_values: List[str]
    ) -> Dict[str, float]:
        """Generate boost factors for ranking."""
        boosts = {}

        type_boosts = {
            QueryType.NUMERICAL_QUERY: {
                'numerical_constraints': 2.0,
                'chunk_priority_critical': 1.5
            },
            QueryType.DEFINITION_QUERY: {
                'definitions': 2.0,
                'chunk_priority_critical': 1.3
            },
            QueryType.PROCEDURE_QUERY: {
                'procedure_steps': 1.8,
                'chunk_priority_high': 1.2
            },
            QueryType.AUTHORITY_QUERY: {
                'authority_modals': 1.7,
                'chunk_priority_high': 1.2
            },
            QueryType.REFERENCE_QUERY: {
                'document_references': 1.5
            },
        }

        boosts.update(type_boosts.get(query_type, {}))

        if numerical_values:
            boosts['exact_numerical_match'] = 2.5
            boosts['partial_numerical_match'] = 1.5

        if entities.numerical_constraints:
            boosts['constraint_match'] = 2.0

        if entities.definitions:
            boosts['definition_match'] = 1.8

        return boosts


__all__ = ["QueryAnalyzer"]
