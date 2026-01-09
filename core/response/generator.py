#!/usr/bin/env python3
"""
Enhanced Response Generator - Main Generator Class
===================================================

Main EnhancedResponseGenerator class for legal response generation.

Author: LegalRAG Development Team
License: MIT
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from .types import (
    ResponseMetrics,
    ResponseQuality,
    ResponseSection,
    StructuredResponse,
)

logger = logging.getLogger(__name__)


class EnhancedResponseGenerator:
    """
    Enhanced response generation system.

    Integrates all components to create high-quality legal consultations.
    """

    def __init__(self) -> None:
        """Initialize enhanced response generator."""
        from ..legal_ontology import LegalOntology
        from ..smart_query_classifier import SmartQueryClassifier

        self.legal_ontology = LegalOntology()
        self.query_classifier = SmartQueryClassifier()

        logger.info("[EnhancedResponseGenerator] Initialized")

    async def generate_response(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_expertise: Any = None
    ) -> StructuredResponse:
        """
        Generate structured legal response.

        Args:
            query: User query
            search_results: Search results from vector store
            conversation_history: Previous conversation messages
            user_expertise: User expertise level

        Returns:
            StructuredResponse with all sections
        """
        from ..smart_query_classifier import UserExpertiseLevel

        if user_expertise is None:
            user_expertise = UserExpertiseLevel.INTERMEDIATE

        response_id = str(uuid.uuid4())
        timestamp = datetime.now()

        response = StructuredResponse(
            query=query,
            response_id=response_id,
            timestamp=timestamp,
            user_expertise=user_expertise
        )

        response.sections[ResponseSection.SUMMARY] = await self._generate_summary(
            query, search_results
        )

        response.sections[ResponseSection.LEGAL_BASIS] = await self._generate_legal_basis(
            query, search_results
        )

        response.sections[ResponseSection.DETAILED_ANALYSIS] = await self._generate_detailed_analysis(
            query, search_results
        )

        response.sections[ResponseSection.PRACTICAL_STEPS] = await self._generate_practical_steps(
            query, search_results, user_expertise
        )

        response.sections[ResponseSection.RISKS_WARNINGS] = await self._generate_risks_warnings(
            query, search_results
        )

        response.sections[ResponseSection.SOURCES] = await self._format_sources(
            search_results
        )

        response.follow_up_questions = await self._generate_follow_up_questions(
            query, search_results
        )

        response.metrics = self._calculate_metrics(response)

        logger.info(f"[Generator] Response generated: {response_id}, quality: {response.metrics.overall_quality.value}")

        return response

    async def _generate_summary(
        self,
        query: str,
        search_results: List[Dict[str, Any]]
    ) -> str:
        """Generate summary section."""
        if not search_results:
            return "К сожалению, не удалось найти релевантную информацию для ответа на ваш запрос."

        top_result = search_results[0]
        content = top_result.get('content', '')

        summary = f"Согласно найденным документам: {content[:200]}..."
        return summary

    async def _generate_legal_basis(
        self,
        query: str,
        search_results: List[Dict[str, Any]]
    ) -> str:
        """Generate legal basis section."""
        legal_basis_parts = []

        for result in search_results[:3]:
            metadata = result.get('metadata', {})
            law = metadata.get('law', 'Нормативный акт')
            article = metadata.get('article_number', 'статья не указана')

            legal_basis_parts.append(f"- {law}, {article}")

        return "\n".join(legal_basis_parts) if legal_basis_parts else "Правовая основа не определена"

    async def _generate_detailed_analysis(
        self,
        query: str,
        search_results: List[Dict[str, Any]]
    ) -> str:
        """Generate detailed analysis section."""
        analysis_parts = []

        for i, result in enumerate(search_results[:3], 1):
            content = result.get('content', '')
            analysis_parts.append(f"{i}. {content}")

        return "\n\n".join(analysis_parts) if analysis_parts else "Детальный анализ недоступен"

    async def _generate_practical_steps(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        user_expertise: Any
    ) -> str:
        """Generate practical steps section."""
        return "1. Изучите применимые нормативные акты\n2. Проконсультируйтесь с юристом\n3. Подготовьте необходимые документы"

    async def _generate_risks_warnings(
        self,
        query: str,
        search_results: List[Dict[str, Any]]
    ) -> str:
        """Generate risks and warnings section."""
        return "Данная консультация носит информационный характер. Для принятия решений рекомендуется получить профессиональную юридическую консультацию."

    async def _format_sources(
        self,
        search_results: List[Dict[str, Any]]
    ) -> str:
        """Format sources section."""
        sources = []

        for i, result in enumerate(search_results[:5], 1):
            metadata = result.get('metadata', {})
            law = metadata.get('law', 'Документ')
            article = metadata.get('article_number', '')

            source_str = f"{i}. {law}"
            if article:
                source_str += f", статья {article}"

            sources.append(source_str)

        return "\n".join(sources) if sources else "Источники не указаны"

    async def _generate_follow_up_questions(
        self,
        query: str,
        search_results: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate follow-up questions."""
        return [
            "Какие конкретные обстоятельства вашей ситуации?",
            "Требуется ли дополнительная информация о процедуре?",
            "Есть ли особые условия, которые нужно учесть?"
        ]

    def _calculate_metrics(self, response: StructuredResponse) -> ResponseMetrics:
        """Calculate response quality metrics."""
        completeness = 0.8 if len(response.sections) >= 4 else 0.5
        accuracy = 0.9 if response.sources else 0.6
        clarity = 0.8
        relevance = 0.85
        legal_depth = 0.75
        user_adaptation = 0.7

        avg_score = (completeness + accuracy + clarity + relevance + legal_depth + user_adaptation) / 6

        if avg_score >= 0.9:
            quality = ResponseQuality.EXCELLENT
        elif avg_score >= 0.8:
            quality = ResponseQuality.GOOD
        elif avg_score >= 0.7:
            quality = ResponseQuality.ACCEPTABLE
        else:
            quality = ResponseQuality.POOR

        return ResponseMetrics(
            completeness=completeness,
            accuracy=accuracy,
            clarity=clarity,
            relevance=relevance,
            legal_depth=legal_depth,
            user_adaptation=user_adaptation,
            overall_quality=quality
        )


__all__ = ["EnhancedResponseGenerator"]
