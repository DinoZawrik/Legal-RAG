#!/usr/bin/env python3
"""
Multimodal Search - Query Analyzer
===================================

Analyzes queries to determine optimal search strategy.

Author: LegalRAG Development Team
License: MIT
"""

import logging
import re
from typing import Dict, List

from .types import QueryAnalysis, QueryType, SearchMode

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Query analyzer for determining optimal search strategy."""

    def __init__(self) -> None:
        """Initialize query analyzer with patterns."""
        self.factual_patterns = [
            r'что такое', r'что означает', r'определение', r'понятие',
            r'что представляет', r'что является', r'суть', r'сущность'
        ]
        self.numerical_patterns = [
            r'какой размер', r'сколько', r'какова сумма', r'какой процент',
            r'какая доля', r'в каком размере', r'какие размеры',
            r'какой максимум', r'какой минимум', r'какой предел'
        ]
        self.procedural_patterns = [
            r'как', r'каким образом', r'порядок', r'процедура',
            r'что нужно', r'как сделать', r'как оформить'
        ]
        self.comparative_patterns = [
            r'в чем разница', r'чем отличается', r'различия',
            r'сравнение', r'сравнить', r'versus'
        ]
        self.constraint_patterns = [
            r'ограничения', r'ограничение', r'лимиты', r'пределы',
            r'максимум', r'минимум', r'не более', r'не менее',
            r'требования', r'условия'
        ]
        self.prohibition_patterns = [
            r'запрет', r'запрещено', r'нельзя', r'не допускается',
            r'недопустимо', r'исключается', r'не может', r'не имеет права'
        ]

        self.legal_concepts = [
            'концессионное соглашение', 'концедент', 'концессионер',
            'плата концедента', 'государственная регистрация',
            'государственное имущество', 'частная собственность',
            'публичное образование', 'муниципальное образование'
        ]

    def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Analyze query and determine search strategy.

        Args:
            query: User query

        Returns:
            QueryAnalysis with extracted information
        """
        query_lower = query.lower()

        query_type = self._classify_query_type(query_lower)
        search_mode = self._determine_search_mode(query_lower, query_type)

        numerical_entities = self._extract_numerical_entities(query)
        legal_concepts = self._extract_legal_concepts(query_lower)
        article_refs = self._extract_article_references(query)
        law_refs = self._extract_law_references(query)

        semantic_keywords = self._extract_semantic_keywords(query_lower)
        structural_keywords = self._extract_structural_keywords(query)
        constraint_keywords = self._extract_constraint_keywords(query_lower)
        prohibition_keywords = self._extract_prohibition_keywords(query_lower)

        return QueryAnalysis(
            original_query=query,
            query_type=query_type,
            search_mode=search_mode,
            extracted_entities=numerical_entities + legal_concepts,
            numerical_constraints=[],
            keywords=semantic_keywords,
            detected_law_references=law_refs,
            detected_article_references=article_refs
        )

    def _classify_query_type(self, query_lower: str) -> QueryType:
        """Classify query type."""
        if any(re.search(pattern, query_lower) for pattern in self.numerical_patterns):
            return QueryType.NUMERICAL
        elif any(re.search(pattern, query_lower) for pattern in self.prohibition_patterns):
            return QueryType.PROHIBITION
        elif any(re.search(pattern, query_lower) for pattern in self.constraint_patterns):
            return QueryType.CONSTRAINT
        elif any(re.search(pattern, query_lower) for pattern in self.procedural_patterns):
            return QueryType.PROCEDURAL
        elif any(re.search(pattern, query_lower) for pattern in self.comparative_patterns):
            return QueryType.COMPARATIVE
        else:
            return QueryType.FACTUAL

    def _determine_search_mode(self, query_lower: str, query_type: QueryType) -> SearchMode:
        """Determine optimal search mode."""
        if query_type == QueryType.NUMERICAL:
            return SearchMode.MULTIMODAL_FULL
        elif query_type == QueryType.CONSTRAINT:
            return SearchMode.HYBRID_ADVANCED
        elif query_type == QueryType.PROHIBITION:
            return SearchMode.HYBRID_ADVANCED
        elif 'статья' in query_lower or 'часть' in query_lower:
            return SearchMode.STRUCTURAL_ONLY
        else:
            return SearchMode.HYBRID_BASIC

    def _extract_numerical_entities(self, query: str) -> List[str]:
        """Extract numerical entities."""
        entities = []
        percent_pattern = r'(\d+(?:[,\.]\d+)?)\s*(?:процент[а-я]*|%)'
        entities.extend(re.findall(percent_pattern, query, re.IGNORECASE))
        money_pattern = r'(\d+(?:\s?\d{3})*(?:[,\.]\d+)?)\s*(?:рубл[ей]*|руб\.?|млн\.?|млрд\.?)'
        entities.extend(re.findall(money_pattern, query, re.IGNORECASE))
        time_pattern = r'(\d+)\s*(?:год[а-я]*|лет|месяц[а-я]*|дн[ей]*)'
        entities.extend(re.findall(time_pattern, query, re.IGNORECASE))
        return entities

    def _extract_legal_concepts(self, query_lower: str) -> List[str]:
        """Extract legal concepts."""
        return [concept for concept in self.legal_concepts if concept in query_lower]

    def _extract_article_references(self, query: str) -> List[str]:
        """Extract article references."""
        pattern = r'(?:статья|статьи|ст\.?)\s*(\d+(?:\.\d+)?)'
        return re.findall(pattern, query, re.IGNORECASE)

    def _extract_law_references(self, query: str) -> List[str]:
        """Extract law references."""
        pattern = r'(\d+)-ФЗ'
        return re.findall(pattern, query, re.IGNORECASE)

    def _extract_semantic_keywords(self, query_lower: str) -> List[str]:
        """Extract semantic keywords."""
        stop_words = {'что', 'такое', 'как', 'это', 'является', 'какой', 'какая', 'какие'}
        words = re.findall(r'\b\w+\b', query_lower)
        return [word for word in words if word not in stop_words and len(word) > 2]

    def _extract_structural_keywords(self, query: str) -> List[str]:
        """Extract structural keywords."""
        structural_terms = []
        if 'статья' in query.lower():
            structural_terms.append('статья')
        if 'часть' in query.lower():
            structural_terms.append('часть')
        if 'пункт' in query.lower():
            structural_terms.append('пункт')
        return structural_terms

    def _extract_constraint_keywords(self, query_lower: str) -> List[str]:
        """Extract constraint keywords."""
        constraint_indicators = [
            'ограничение', 'ограничения', 'лимит', 'предел',
            'максимум', 'минимум', 'не более', 'не менее',
            'требование', 'условие', 'размер'
        ]
        return [term for term in constraint_indicators if term in query_lower]

    def _extract_prohibition_keywords(self, query_lower: str) -> List[str]:
        """Extract prohibition keywords."""
        prohibition_indicators = [
            'запрет', 'запрещено', 'нельзя', 'не допускается',
            'недопустимо', 'исключается', 'не может', 'не имеет права'
        ]
        return [term for term in prohibition_indicators if term in query_lower]


__all__ = ["QueryAnalyzer"]
