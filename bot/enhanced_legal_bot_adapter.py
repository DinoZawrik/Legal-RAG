"""
Адаптер для интеграции Enhanced Legal System с Telegram ботом.
Предоставляет совместимый интерфейс с UnifiedAISystem.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

# Импорт Enhanced Legal System
from core.enhanced_legal_assistant import (
    EnhancedLegalAssistant,
    LegalConsultationRequest,
    LegalConsultationResponse
)
from core.smart_query_classifier import UserExpertiseLevel
from core.infrastructure_suite import initialize_core_system

logger = logging.getLogger(__name__)


class EnhancedLegalBotAdapter:
    """
    Адаптер для использования Enhanced Legal System в Telegram боте.
    Обеспечивает совместимость с интерфейсом UnifiedAISystem.
    """

    def __init__(self):
        self.initialized = False
        self.enhanced_assistant = None

    async def initialize(self, vector_store=None):
        """Инициализация Enhanced Legal System."""
        try:
            logger.info(" Инициализация Enhanced Legal Bot Adapter...")

            # Инициализация базовой системы
            await initialize_core_system()

            # Создание Enhanced Legal Assistant
            self.enhanced_assistant = EnhancedLegalAssistant()

            self.initialized = True
            logger.info(" Enhanced Legal Bot Adapter инициализирован")

        except Exception as e:
            logger.error(f" Ошибка инициализации Enhanced Legal Bot Adapter: {e}")
            self.initialized = False
            raise

    async def process_query(self, query: str, query_type: str = "auto",
                          context: Optional[List[Dict[str, str]]] = None,
                          user_id: str = "telegram_user",
                          **kwargs) -> Dict[str, Any]:
        """
        Обработка запроса через Enhanced Legal System.
        Совместимый интерфейс с UnifiedAISystem.process_query.
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "Enhanced Legal System not initialized",
                "response": "Система не инициализирована"
            }

        try:
            logger.info(f" Обработка запроса через Enhanced Legal System: {query[:100]}...")

            # Подготовка истории разговора
            conversation_history = []
            if context:
                for entry in context:
                    if isinstance(entry, dict):
                        conversation_history.append(entry)

            # Автоматическое определение уровня экспертизы пользователя
            # По умолчанию INTERMEDIATE для обычных пользователей
            user_expertise = self._determine_user_expertise(query, conversation_history)

            # Создание запроса на консультацию
            consultation_request = LegalConsultationRequest(
                query=query,
                user_id=user_id,
                user_expertise=user_expertise,
                conversation_history=conversation_history,
                timestamp=datetime.now()
            )

            # Обработка через Enhanced Legal Assistant
            consultation_response = await self.enhanced_assistant.process_legal_consultation(
                consultation_request
            )

            # Преобразование ответа в формат совместимый с UnifiedAISystem
            response_data = self._format_response_for_bot(consultation_response)

            logger.info(f" Ответ получен (качество: {consultation_response.validation_report.quality_grade.value})")

            return response_data

        except Exception as e:
            logger.error(f" Ошибка обработки запроса: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"Извините, произошла ошибка при обработке вашего вопроса: {str(e)}"
            }

    def _determine_user_expertise(self, query: str, history: List[Dict]) -> UserExpertiseLevel:
        """Определяет уровень экспертизы пользователя на основе запроса и истории."""
        # Анализ сложности запроса
        legal_terms = [
            "статья", "закон", "кодекс", "постановление", "указ", "норма",
            "юрисдикция", "правоотношения", "правосубъектность", "деликт",
            "коллизия", "преюдиция", "казус", "прецедент", "диспозиция"
        ]

        complex_terms = [
            "коллизия", "преюдиция", "казус", "прецедент", "диспозиция",
            "правосубъектность", "юрисдикция", "деликт"
        ]

        query_lower = query.lower()

        # Подсчет специальных терминов
        legal_term_count = sum(1 for term in legal_terms if term in query_lower)
        complex_term_count = sum(1 for term in complex_terms if term in query_lower)

        # Анализ истории - если есть много юридических запросов
        history_legal_count = 0
        if history:
            for entry in history[-5:]: # Последние 5 сообщений
                content = entry.get("content", "").lower()
                history_legal_count += sum(1 for term in legal_terms if term in content)

        # Определение уровня
        if complex_term_count >= 2 or (legal_term_count >= 3 and history_legal_count >= 5):
            return UserExpertiseLevel.EXPERT
        elif legal_term_count >= 2 or history_legal_count >= 3:
            return UserExpertiseLevel.ADVANCED
        elif legal_term_count >= 1 or history_legal_count >= 1:
            return UserExpertiseLevel.INTERMEDIATE
        else:
            return UserExpertiseLevel.BEGINNER

    def _format_response_for_bot(self, consultation_response: LegalConsultationResponse) -> Dict[str, Any]:
        """Форматирует ответ Enhanced Legal System для Telegram бота."""

        structured_response = consultation_response.structured_response
        validation_report = consultation_response.validation_report

        # Формирование основного текста ответа
        response_parts = []

        # Краткое резюме
        if hasattr(structured_response, 'sections') and 'summary' in structured_response.sections:
            response_parts.append(f" **Краткий ответ:**\n{structured_response.sections['summary']}")

        # Правовая основа
        if hasattr(structured_response, 'sections') and 'legal_basis' in structured_response.sections:
            response_parts.append(f"\n **Правовая основа:**\n{structured_response.sections['legal_basis']}")

        # Практические рекомендации
        if hasattr(structured_response, 'sections') and 'recommendations' in structured_response.sections:
            response_parts.append(f"\n **Рекомендации:**\n{structured_response.sections['recommendations']}")

        # Источники
        sources_text = self._format_sources(structured_response)
        if sources_text:
            response_parts.append(f"\n **Источники:**\n{sources_text}")

        # Предупреждения (если есть)
        if hasattr(structured_response, 'warnings') and structured_response.warnings:
            warnings_text = "\n".join(f" {warning}" for warning in structured_response.warnings)
            response_parts.append(f"\n{warnings_text}")

        # Качество ответа (если низкое)
        if validation_report.overall_score < 0.7:
            response_parts.append(f"\n *Качество ответа: {validation_report.quality_grade.value}. Рекомендуется проконсультироваться со специалистом.*")

        response_text = "\n".join(response_parts)

        # Если ответ пустой, используем fallback
        if not response_text.strip():
            response_text = "Извините, не удалось сформулировать полный ответ на ваш вопрос. Попробуйте переформулировать запрос."

        return {
            "success": True,
            "response": response_text,
            "sources": self._extract_source_list(structured_response),
            "confidence": consultation_response.confidence_score,
            "processing_time": consultation_response.processing_time,
            "quality_grade": validation_report.quality_grade.value,
            "metadata": {
                "request_id": consultation_response.request_id,
                "components_used": consultation_response.components_used,
                "total_issues": validation_report.total_issues,
                "critical_issues": validation_report.critical_issues
            }
        }

    def _format_sources(self, structured_response) -> str:
        """Форматирует источники для отображения в боте."""
        if not hasattr(structured_response, 'sources') or not structured_response.sources:
            return ""

        sources_list = []
        for i, source in enumerate(structured_response.sources[:5], 1): # Максимум 5 источников
            if hasattr(source, 'document_title'):
                title = source.document_title
            elif isinstance(source, dict):
                title = source.get('document_title', source.get('title', 'Документ'))
            else:
                title = str(source)

            sources_list.append(f"{i}. {title}")

        return "\n".join(sources_list)

    def _extract_source_list(self, structured_response) -> List[str]:
        """Извлекает список источников для метаданных."""
        if not hasattr(structured_response, 'sources') or not structured_response.sources:
            return []

        sources = []
        for source in structured_response.sources:
            if hasattr(source, 'document_title'):
                sources.append(source.document_title)
            elif isinstance(source, dict):
                sources.append(source.get('document_title', source.get('title', 'Неизвестный документ')))
            else:
                sources.append(str(source))

        return sources

    # Дополнительные методы для совместимости с UnifiedAISystem

    async def process_question(self, question: str, use_optimal_rag: bool = True, **kwargs) -> Dict[str, Any]:
        """Совместимость с process_question методом."""
        return await self.process_query(question, **kwargs)

    def get_system_status(self) -> Dict[str, Any]:
        """Получение статуса системы."""
        if self.enhanced_assistant:
            return self.enhanced_assistant.get_system_status()
        return {"status": "not_initialized"}

    def get_capabilities(self) -> List[str]:
        """Получение списка возможностей системы."""
        if self.enhanced_assistant:
            return self.enhanced_assistant.get_capabilities()
        return []


# Глобальный экземпляр для использования в боте
enhanced_legal_bot_adapter = EnhancedLegalBotAdapter()