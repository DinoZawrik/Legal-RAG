#!/usr/bin/env python3
"""
🤖 AI QA Pipeline
Система вопрос-ответ для работы с документами.

Включает функциональность:
- QAPipeline: основная система вопрос-ответ
- RAG оптимизация и конфигурация
- Поиск релевантных чанков в векторной БД
- Генерация ответов на основе документов (а не собственных знаний модели)
- Пакетная обработка вопросов
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any

from core.ai_inference_core import EnhancedInferenceEngine

# RAG Optimizer integration
try:
    from core.rag_optimizer import get_rag_optimizer, RAGConfig
    RAG_OPTIMIZER_AVAILABLE = True
except ImportError:
    RAG_OPTIMIZER_AVAILABLE = False
    logging.warning("⚠️ RAG Optimizer недоступен")

logger = logging.getLogger(__name__)


class QAPipeline:
    """
    Система вопрос-ответ для работы с документами.
    Объединяет функциональность из qa_pipeline.py

    КРИТИЧЕСКИ ВАЖНО: Система должна опираться на документы в БД,
    а не на собственные знания модели (требование из complex_task.txt)
    """

    def __init__(self, inference_engine: EnhancedInferenceEngine):
        self.inference_engine = inference_engine
        self.vector_store = None
        self.retrieval_config = {
            "max_chunks": 10,  # Увеличено с 5 до 10 для лучшего покрытия
            "similarity_threshold": 0.7,
            "max_chunk_length": 1000
        }

        # RAG Optimizer integration для Graph RAG, Self-RAG поддержки
        self.rag_optimizer = None
        self.current_rag_config = None

        if RAG_OPTIMIZER_AVAILABLE:
            try:
                self.rag_optimizer = get_rag_optimizer()
                # Используем сбалансированную конфигурацию по умолчанию
                self.current_rag_config = self.rag_optimizer.get_config("balanced")
                if self.current_rag_config:
                    self._apply_rag_config(self.current_rag_config)
                    logger.info(f"✅ RAG конфигурация '{self.current_rag_config.name}' применена")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации RAG Optimizer: {e}")

    def _apply_rag_config(self, config: RAGConfig):
        """Применение конфигурации RAG к системе поиска."""
        self.retrieval_config.update({
            "max_chunks": config.max_chunks,
            "similarity_threshold": config.similarity_threshold,
            "max_chunk_length": config.max_chunk_length
        })

    def set_rag_config(self, config_name: str) -> bool:
        """
        Установка конфигурации RAG по имени.

        Args:
            config_name: Имя конфигурации из RAG Optimizer

        Returns:
            True если конфигурация применена успешно
        """
        if not self.rag_optimizer:
            logger.warning("⚠️ RAG Optimizer недоступен")
            return False

        config = self.rag_optimizer.get_config(config_name)
        if not config:
            logger.error(f"❌ Конфигурация '{config_name}' не найдена")
            return False

        try:
            self._apply_rag_config(config)
            self.current_rag_config = config
            logger.info(f"✅ RAG конфигурация изменена на '{config_name}'")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка применения конфигурации '{config_name}': {e}")
            return False

    def get_available_configs(self) -> Dict[str, str]:
        """Получение списка доступных RAG конфигураций."""
        if not self.rag_optimizer:
            return {}
        return self.rag_optimizer.list_configs()

    def get_current_config_info(self) -> Dict[str, Any]:
        """Получение информации о текущей конфигурации."""
        if not self.current_rag_config:
            return {"config_name": "default", "details": self.retrieval_config}

        return {
            "config_name": self.current_rag_config.name,
            "description": self.current_rag_config.description,
            "details": {
                "max_chunks": self.current_rag_config.max_chunks,
                "similarity_threshold": self.current_rag_config.similarity_threshold,
                "max_chunk_length": self.current_rag_config.max_chunk_length,
                "enable_reranking": self.current_rag_config.enable_reranking,
                "adaptive_threshold": self.current_rag_config.adaptive_threshold
            }
        }

    async def initialize(self, vector_store):
        """Инициализация QA pipeline с vector store."""
        self.vector_store = vector_store
        logger.info("✅ QA Pipeline инициализирован")

    async def retrieve_relevant_chunks(self, query: str) -> List[Dict[str, Any]]:
        """
        Поиск релевантных чанков для вопроса из векторной БД.

        КРИТИЧЕСКИ ВАЖНО: Использует только документы из БД,
        НЕ собственные знания модели (требование из complex_task.txt)
        """
        try:
            if not self.vector_store:
                logger.warning("❌ Vector store не инициализирован - нет доступа к документам БД")
                return []

            # Поиск похожих документов через similarity_search
            if hasattr(self.vector_store, 'similarity_search'):
                # Используем стандартный метод LangChain Chroma
                docs = self.vector_store.similarity_search(
                    query,
                    k=self.retrieval_config["max_chunks"]
                )

                # Преобразуем результаты в нужный формат
                results = []
                for doc in docs:
                    results.append({
                        "text": doc.page_content,
                        "metadata": doc.metadata,
                        "similarity": 1.0  # Chroma не возвращает оценку схожести напрямую
                    })

            elif hasattr(self.vector_store, 'search_similar'):
                # Используем наш кастомный метод
                results = await self.vector_store.search_similar(
                    query=query,
                    limit=self.retrieval_config["max_chunks"]
                )
            else:
                logger.warning("Vector store не поддерживает поиск")
                return []

            # Фильтрация по порогу схожести
            # Для ChromaDB используется distance (чем меньше, тем лучше), конвертируем в similarity
            filtered_results = []
            threshold = self.retrieval_config["similarity_threshold"]

            for result in results:
                if "distance" in result:
                    # ChromaDB: distance -> similarity (1 - distance)
                    similarity = 1 - result["distance"]
                    result["similarity"] = similarity
                    if similarity >= threshold:
                        filtered_results.append(result)
                elif result.get("similarity", 0) >= threshold:
                    # Прямое значение similarity
                    filtered_results.append(result)
                else:
                    # Для Chroma без distance - принимаем все результаты
                    if "distance" not in result and "similarity" not in result:
                        filtered_results.append(result)

            # Ограничение длины чанков
            for result in filtered_results:
                if len(result["text"]) > self.retrieval_config["max_chunk_length"]:
                    result["text"] = result["text"][:self.retrieval_config["max_chunk_length"]] + "..."

            logger.info(f"🔍 Найдено {len(filtered_results)} релевантных чанков из БД")
            return filtered_results

        except Exception as e:
            logger.error(f"❌ Ошибка поиска релевантных чанков: {e}")
            return []

    async def answer_question(self, question: str,
                            use_context: bool = True,
                            context_override: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Ответ на вопрос с использованием контекста документов из БД.

        КРИТИЧЕСКИ ВАЖНО: Система должна отвечать ТОЛЬКО на основе документов БД,
        а не собственных знаний модели (требование из complex_task.txt)
        """
        try:
            context = []
            retrieved_chunks = []

            if use_context and not context_override:
                # Поиск релевантного контекста из БД
                retrieved_chunks = await self.retrieve_relevant_chunks(question)
                context = [chunk["text"] for chunk in retrieved_chunks]
            elif context_override:
                context = context_override

            # Проверка наличия контекста из БД
            if not context and use_context:
                logger.warning("❌ Нет контекста из БД - невозможно дать точный ответ")
                return {
                    "success": False,
                    "error": "Нет релевантных документов в БД",
                    "response": "Для ответа на этот вопрос необходимы соответствующие документы в базе данных.",
                    "question": question,
                    "context_used": False,
                    "context_chunks_count": 0
                }

            # Формирование промпта для ответа на основе документов БД
            if context:
                enhanced_question = f"""
                ЗАДАЧА: Ответьте на вопрос, анализируя предоставленные выдержки из нормативных документов из БД.

                ВОПРОС: {question}

                КРИТИЧЕСКИ ВАЖНЫЕ ИНСТРУКЦИИ ПО ССЫЛКАМ:
                1. Внимательно изучите ВСЕ предоставленные выдержки из документов БД
                2. Найдите релевантную информацию и синтезируйте полный ответ
                3. ДЛЯ КАЖДОГО ФАКТА ОБЯЗАТЕЛЬНО указывайте ПОЛНОЕ название документа:
                   ✅ ПРАВИЛЬНО: "согласно Постановлению Правительства РФ от 22.10.2012 N 1075"
                   ✅ ПРАВИЛЬНО: "в соответствии с Федеральным законом от 27.07.2010 N 190-ФЗ"
                   ❌ НЕПРАВИЛЬНО: "согласно постановлению" (без номера и даты)
                   ❌ НЕПРАВИЛЬНО: "согласно параграфу 70" (без названия документа)
                4. НЕ используйте слова "пункт", "фрагмент", "чанк" в ссылках
                5. Указывайте полное название документа с номером и датой для каждой ссылки
                6. Если некоторая информация отсутствует в БД - укажите это в конце ответа
                7. НЕ отказывайтесь отвечать, если есть хотя бы частичная информация в БД
                8. ОТВЕЧАЙТЕ ТОЛЬКО НА ОСНОВЕ ДОКУМЕНТОВ БД - НЕ используйте собственные знания

                КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА ФОРМАТИРОВАНИЯ:
                • НАЗВАНИЕ ДОКУМЕНТА ВСЕГДА НА ОДНОЙ СТРОКЕ - никогда не разбивайте на несколько строк
                • Используйте **жирный шрифт** для заголовков разделов
                • Используйте • для списков (не звездочки *)
                • Короткие абзацы - максимум 2-3 предложения в абзаце
                • Одна пустая строка между разделами
                • НЕ переносите названия законов, постановлений, приказов на новую строку

                СТРУКТУРА ОТВЕТА:
                **Основная информация**
                • Ключевые пункты по теме
                • Основные требования или определения

                **Детали и особенности**
                • Дополнительные условия
                • Исключения или специальные случаи

                **Практическое применение**
                • Выводы и рекомендации

                Дайте максимально полный и структурированный ответ на основе имеющихся данных БД.
                """
            else:
                enhanced_question = f"""
                ВОПРОС: {question}

                ВАЖНО: Документы не предоставлены из БД. Сообщите, что для точного ответа необходимы
                соответствующие нормативные документы по данной теме в базе данных.
                """

            # Генерация ответа
            response = await self.inference_engine.generate_response(
                prompt=enhanced_question,
                system_prompt_key="question_answering",
                context=context
            )

            # Проверка на пустой ответ и диагностика
            response_text = response.get("response", "")

            # ✅ НОВОЕ: Answer Verification Layer
            # Проверяем корректность ответа (цитирования, галлюцинации)
            if response_text and retrieved_chunks:
                try:
                    from core.answer_verifier import verify_answer

                    verification = verify_answer(
                        answer=response_text,
                        source_chunks=retrieved_chunks,
                        min_confidence=0.6
                    )

                    # Добавляем warning если низкая уверенность
                    if not verification.is_valid:
                        from core.answer_verifier import get_answer_verifier
                        verifier = get_answer_verifier()
                        warning_msg = verifier.format_warning_message(verification)
                        response_text += warning_msg
                        response["response"] = response_text
                        logger.warning(f"⚠️ Answer verification failed: confidence={verification.confidence:.2f}")

                    # Добавляем метаданные о верификации
                    response["verification"] = {
                        "is_valid": verification.is_valid,
                        "confidence": verification.confidence,
                        "citations_valid": verification.citations_valid,
                        "warnings": verification.warnings
                    }

                except Exception as e:
                    logger.warning(f"⚠️ Answer verification error: {e}")
                    # Продолжаем без верификации если ошибка
            if not response_text or response_text.strip() == "":
                logger.warning(f"❌ ПУСТОЙ ОТВЕТ для вопроса: {question}")
                logger.warning(f"   - Контекст из БД предоставлен: {len(context) > 0}")
                logger.warning(f"   - Количество чанков из БД: {len(context)}")
                logger.warning(f"   - Успешность LLM: {response.get('success', False)}")
                logger.warning(f"   - Ошибка LLM: {response.get('error', 'Нет ошибки')}")
                if context:
                    logger.warning(f"   - Первый чанк из БД: {context[0][:200]}...")

                # Fallback НЕ используем собственные знания - только БД
                return {
                    "success": False,
                    "error": "Пустой ответ от модели несмотря на наличие контекста БД",
                    "response": "Не удалось сформировать ответ на основе документов БД.",
                    "question": question,
                    "context_used": len(context) > 0,
                    "context_chunks_count": len(context)
                }

            # Дополнение результата информацией о контексте БД
            response.update({
                "question": question,
                "context_used": len(context) > 0,
                "context_chunks_count": len(context),
                "retrieved_chunks": retrieved_chunks[:3],  # Первые 3 для показа
                "confidence": self._calculate_confidence(response, context),
                "source": "database_documents"  # Указываем что источник - БД
            })

            return response

        except Exception as e:
            logger.error(f"❌ Ошибка ответа на вопрос: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "Извините, не удалось ответить на вопрос.",
                "question": question,
                "context_used": False,
                "source": "error"
            }

    def _calculate_confidence(self, response: Dict[str, Any], context: List[str]) -> float:
        """Расчет уверенности в ответе на основе контекста БД."""
        try:
            confidence = 0.5  # Базовая уверенность

            # Увеличение уверенности при наличии контекста из БД
            if context:
                confidence += 0.2

            # Анализ качества ответа
            if response.get("success"):
                response_text = response.get("response", "")

                # Длина ответа
                if len(response_text) > 100:
                    confidence += 0.1

                # Наличие конкретных деталей
                if any(keyword in response_text.lower() for keyword in
                      ["согласно", "в соответствии", "статья", "пункт", "раздел"]):
                    confidence += 0.1

                # Отсутствие неопределенности
                uncertainty_words = ["возможно", "вероятно", "может быть", "не уверен"]
                if not any(word in response_text.lower() for word in uncertainty_words):
                    confidence += 0.1

            return min(confidence, 1.0)

        except Exception:
            return 0.5

    async def batch_qa(self, questions: List[str]) -> List[Dict[str, Any]]:
        """Пакетная обработка вопросов с использованием документов БД."""
        results = []

        for i, question in enumerate(questions):
            logger.info(f"🤔 Обработка вопроса {i+1}/{len(questions)} (только на основе БД)")

            result = await self.answer_question(question)
            result["question_index"] = i
            results.append(result)

            # Небольшая пауза между запросами
            await asyncio.sleep(0.1)

        return results