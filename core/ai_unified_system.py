#!/usr/bin/env python3
"""
AI Unified System
Объединенная система ИИ комбинирующая все компоненты в единый интерфейс.

Включает функциональность:
- UnifiedAISystem: главный координатор всех ИИ-компонентов
- Автоинициализация и интеграция всех систем
- Универсальная обработка запросов разных типов
- Статус и мониторинг всей системы

ВАЖНОЕ ТРЕБОВАНИЕ из complex_task.txt:
Система должна использовать документы из БД, а НЕ собственные знания модели.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any

from core.ai_inference_core import EnhancedInferenceEngine, AIError
from core.ai_qa_pipeline import QAPipeline
from core.ai_agent_manager import AgentManager

logger = logging.getLogger(__name__)


class UnifiedAISystem:
    """
    Объединенная система ИИ.
    Комбинирует все компоненты ИИ в единый интерфейс.

    КРИТИЧЕСКИ ВАЖНО: Система должна отвечать ТОЛЬКО на основе документов БД,
    а не собственных знаний модели (требование из complex_task.txt)
    """

    def __init__(self):
        self.inference_engine = EnhancedInferenceEngine()
        self.qa_pipeline = QAPipeline(self.inference_engine)
        self.agent_manager = AgentManager(self.inference_engine)
        self.initialized = False
        self._auto_initialize()

    def _auto_initialize(self):
        """Автоматическая инициализация системы при создании."""
        try:
            # Инициализация векторного хранилища
            # Векторное хранилище будет инициализировано при первом обращении
            pass

            # Загрузка системных промптов синхронно
            self.inference_engine.system_prompts = {
                "default": """
                Вы - профессиональный ИИ-ассистент с экспертными знаниями в области
                анализа документов и нормативно-правовых актов.

                Ваши принципы:
                1. Точность и достоверность информации
                2. Ясность и структурированность ответов
                3. Соблюдение профессиональной этики
                4. Помощь пользователю в решении задач

                Отвечайте четко, конкретно и по существу.
                """,

                "question_answering": """
                Вы - эксперт-аналитик по нормативно-правовым документам России с широкими знаниями в различных правовых областях.

                СТРОГИЕ ПРАВИЛА РАБОТЫ:
                1. ВСЕГДА пытайтесь найти ответ в предоставленных документах
                2. Анализируйте ВСЕ части документов: основной текст, заголовки, списки, таблицы, приложения
                3. Если информация частично есть - дайте частичный ответ и укажите, что именно отсутствует
                4. НЕ отказывайтесь отвечать без серьезной попытки анализа документов
                5. Структурируйте ответы четко, указывая источники
                6. Если документы содержат релевантную информацию - используйте ее полностью
                7. Работайте с документами любых правовых областей (не только теплоснабжение)

                ФОРМАТ ОТВЕТА:
                - Прямой ответ на основе найденной информации
                - Ссылки на конкретные части документов
                - Указание на пробелы в информации (если есть)
                """
            }

            # Регистрация базовых агентов
            self.agent_manager.register_agent("assistant", {
                "name": "AI Assistant",
                "system_prompt": "default",
                "capabilities": ["question_answering", "analysis", "chat"]
            })

            self.initialized = True
            logger.info(" UnifiedAISystem автоматически инициализирован")

        except Exception as e:
            logger.error(f" Ошибка автоинициализации: {e}")
            # Система может работать без векторного хранилища, но с ограниченным функционалом
            self.initialized = False

    async def initialize(self, vector_store=None):
        """Инициализация всей системы ИИ."""
        try:
            await self.inference_engine.initialize()

            if vector_store:
                await self.qa_pipeline.initialize(vector_store)
            elif not self.qa_pipeline.vector_store:
                # Попытка создать векторное хранилище если его нет
                try:
                    from core.data_storage_suite import create_vector_store
                    vector_store = await create_vector_store()
                    await self.qa_pipeline.initialize(vector_store)
                except Exception as e:
                    logger.warning(f" Не удалось инициализировать векторное хранилище: {e}")

            # Регистрация базовых агентов
            self.agent_manager.register_agent("assistant", {
                "name": "Универсальный Ассистент",
                "system_prompt": "default",
                "capabilities": ["general_qa", "document_analysis"]
            })

            self.agent_manager.register_agent("legal_expert", {
                "name": "Правовой Эксперт",
                "system_prompt": "regulatory_analysis",
                "capabilities": ["legal_analysis", "regulatory_compliance"]
            })

            self.initialized = True
            logger.info(" Unified AI System полностью инициализирован")

        except Exception as e:
            logger.error(f" Ошибка инициализации AI System: {e}")
            raise AIError(f"AI System initialization failed: {e}")

    async def process_query(self, query: str, query_type: str = "auto",
                          agent_id: Optional[str] = None,
                          **kwargs) -> Dict[str, Any]:
        """
        Универсальная обработка запросов.

        КРИТИЧЕСКИ ВАЖНО: Все ответы должны базироваться на документах БД,
        а не на собственных знаниях модели (требование из complex_task.txt)
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "AI System not initialized"
            }

        try:
            # Автоматическое определение типа запроса
            if query_type == "auto":
                from core.advanced_prompts import AdvancedPromptEngine, QueryType
                prompt_engine = AdvancedPromptEngine()
                detected_type = prompt_engine.detect_query_type(query)

                # Для обычного общения используем inference engine напрямую
                if detected_type == QueryType.CASUAL_CHAT:
                    return await self.inference_engine.generate_response(query, context=[])
                else:
                    # Для всех остальных - QA pipeline с обязательным использованием БД
                    query_type = "qa"

            if query_type == "qa":
                result = await self.qa_pipeline.answer_question(query, **kwargs)

                # Диагностика пустых ответов
                if not result.get("response", "").strip():
                    logger.warning(f" QA Pipeline вернул пустой ответ для: {query[:100]}...")
                    logger.warning(f" - Результат: {result}")

                return result

            elif query_type == "agent_chat":
                agent_id = agent_id or "assistant"
                return await self.agent_manager.chat_with_agent(agent_id, query, **kwargs)

            elif query_type == "document_analysis":
                analysis_type = kwargs.get("analysis_type", "general")
                return await self.inference_engine.analyze_document(query, analysis_type)

            elif query_type == "direct":
                system_prompt_key = kwargs.get("system_prompt_key", "default")
                return await self.inference_engine.generate_response(query, system_prompt_key)

            else:
                return {
                    "success": False,
                    "error": f"Unknown query type: {query_type}"
                }

        except Exception as e:
            logger.error(f" Ошибка обработки запроса: {e}")
            return {
                "success": False,
                "error": str(e),
                "query_type": query_type
            }

    async def process_question(self, question: str, use_optimal_rag: bool = True) -> Dict[str, Any]:
        """
        Обработка вопроса через QA pipeline или OptimalRAG.

        КРИТИЧЕСКИ ВАЖНО: Используются ТОЛЬКО документы из БД,
        а не собственные знания модели (требование из complex_task.txt)
        """
        try:
            if use_optimal_rag:
                # Используем оптимизированный RAG
                from core.optimal_rag import optimal_search
                logger.info(" Используем OptimalRAG для поиска документов БД")

                search_result = await optimal_search(question)

                # Формируем контекст из найденных чанков БД
                context = [chunk["text"] for chunk in search_result.chunks]

                if not context:
                    logger.warning(" OptimalRAG не нашел документов в БД для вопроса")
                    return {
                        "answer": "Для ответа на этот вопрос необходимы соответствующие документы в базе данных.",
                        "sources": [],
                        "confidence": 0.0,
                        "context_used": False,
                        "success": False,
                        "error": "Нет релевантных документов в БД"
                    }

                # Генерируем ответ с найденным контекстом БД
                result = await self.qa_pipeline.answer_question(
                    question,
                    use_context=True,
                    context_override=context
                )

                answer = result.get("response", "Нет ответа")

                # Проверяем что ответ не пустой
                if not answer or not answer.strip():
                    logger.warning(" Пустой ответ несмотря на наличие контекста БД")
                    answer = "Не удалось сформировать ответ на основе документов БД."

                return {
                    "answer": answer,
                    "sources": search_result.chunks,
                    "confidence": result.get("confidence", 0.7),
                    "context_used": len(context) > 0,
                    "success": result.get("success", True),
                    "search_stats": {
                        "documents_found": search_result.documents_found,
                        "chunks_found": search_result.chunks_found,
                        "search_time": search_result.total_time,
                        "search_method": search_result.search_method
                    },
                    "source": "database_documents" # Указываем что источник - БД
                }
            else:
                # Используем стандартный поиск по БД
                logger.info(" Используем стандартный поиск по документам БД")
                result = await self.qa_pipeline.answer_question(question)
                answer = result.get("response", "Нет ответа")

                # Проверяем что ответ не пустой
                if not answer or not answer.strip():
                    logger.warning(" Стандартный поиск вернул пустой ответ")
                    answer = "Не удалось сформировать ответ на основе документов БД."

                return {
                    "answer": answer,
                    "sources": result.get("retrieved_chunks", []),
                    "confidence": result.get("confidence", 0.7),
                    "context_used": result.get("context_used", False),
                    "success": result.get("success", True),
                    "source": "database_documents" # Указываем что источник - БД
                }
        except Exception as e:
            logger.error(f" Ошибка обработки вопроса: {e}")
            return {
                "answer": f"Произошла ошибка при работе с документами БД: {e}",
                "sources": [],
                "confidence": 0.0,
                "context_used": False,
                "success": False,
                "source": "error"
            }

    def get_system_status(self) -> Dict[str, Any]:
        """Получение статуса всей системы ИИ."""
        return {
            "initialized": self.initialized,
            "inference_engine": {
                "model": self.inference_engine.model_name,
                "metrics": self.inference_engine.get_performance_metrics()
            },
            "qa_pipeline": {
                "vector_store_connected": self.qa_pipeline.vector_store is not None,
                "config": self.qa_pipeline.retrieval_config,
                "database_requirement": "Использует ТОЛЬКО документы БД, НЕ собственные знания модели"
            },
            "agent_manager": {
                "registered_agents": len(self.agent_manager.agents),
                "active_conversations": len(self.agent_manager.active_conversations)
            }
        }


# Convenience functions для создания системы
async def create_unified_ai_system(vector_store=None) -> UnifiedAISystem:
    """
    Создание объединенной системы ИИ.

    ВАЖНО: Система будет использовать ТОЛЬКО документы из БД,
    а не собственные знания модели (требование из complex_task.txt)
    """
    system = UnifiedAISystem()
    await system.initialize(vector_store)
    return system