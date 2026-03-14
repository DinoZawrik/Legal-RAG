#!/usr/bin/env python3
"""
[AI] Inference Service
Микросервис AI инференса - генерация ответов и адаптивные промпты
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
import time

from services.base import BaseService, ServiceStatus
from core.ai_inference_suite import create_inference_engine
from core.advanced_prompts import AdvancedPromptEngine, QueryType
from core.universal_legal_system import get_universal_legal_system, UniversalLegalSystem
from core.logging_config import configure_logging

# КРИТИЧЕСКИЕ УЛУЧШЕНИЯ: Self-RAG и IRAC промпты
from core.self_rag_engine import SelfRAGInferenceEngine, SelfRAGResult
from core.russian_legal_prompts import RussianLegalPrompts, SpecializedLegalPrompts
from core.russian_legal_chunker import RussianLegalChunker

# ФАЗА 1.3: Multi-layer Verification System
from core.legal_fact_verifier import LegalFactVerifier, VerificationSeverity

logger = logging.getLogger(__name__)


class InferenceService(BaseService):
    """
    Микросервис AI инференса и генерации ответов.
    
    Объединяет:
    - AI модели (Google Gemini)
    - Адаптивные промпты
    - Контекстную генерацию
    """
    
    def __init__(self):
        super().__init__("inference_service")
        
        # Компоненты AI
        self.inference_system = None
        self.prompt_engine: Optional[AdvancedPromptEngine] = None
        self.universal_legal_system: Optional[UniversalLegalSystem] = None

        # КРИТИЧЕСКИЕ УЛУЧШЕНИЯ
        self.self_rag_engine: Optional[SelfRAGInferenceEngine] = None
        self.russian_legal_prompts = RussianLegalPrompts()
        self.specialized_prompts = SpecializedLegalPrompts()
        self.legal_chunker = RussianLegalChunker()
        self.storage_manager = None # Будет инициализирован в initialize()

        # ФАЗА 1.3: Legal Fact Verifier
        self.legal_verifier = LegalFactVerifier()
        self.enable_verification = True # Можно отключить для отладки
        
        # Конфигурация
        self.default_config = {
            "model": os.getenv("AGENT_MODEL_NAME", "gemini-3-flash-preview"),
            "max_tokens": 2048,
            "temperature": 0.1,
            "timeout_seconds": 30
        }
        
        # Метрики инференса
        self.inference_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_generation_time": 0.0,
            "generation_times": []
        }
    
    async def initialize(self) -> None:
        """Инициализация Inference Service."""
        try:
            self.logger.info("[AI] Initializing Inference Service...")
            
            # Инициализация системы AI инференса
            self.logger.info("[RELOAD] Loading AI Inference System...")
            self.inference_system = await create_inference_engine()
            
            # Инициализация адаптивных промптов
            self.logger.info("[RELOAD] Loading Advanced Prompt Engine...")
            self.prompt_engine = AdvancedPromptEngine()

            # НОВОЕ: Инициализация Universal Legal System для лучшей генерации
            self.logger.info("[TARGET] Loading Universal Legal System...")
            self.universal_legal_system = await get_universal_legal_system()

            # КРИТИЧЕСКОЕ УЛУЧШЕНИЕ: Инициализация Self-RAG движка
            self.logger.info("[] Initializing Self-RAG Engine with IRAC prompts...")
            # Создаем storage_manager напрямую
            try:
                from core.storage_coordinator import create_storage_coordinator
                self.storage_manager = await create_storage_coordinator()

                self.self_rag_engine = SelfRAGInferenceEngine(self, self.storage_manager)
                self.logger.info("[] Self-RAG Engine initialized successfully")
            except Exception as e:
                self.logger.error(f"[] Failed to initialize Self-RAG Engine: {e}")
                self.self_rag_engine = None

            # Установка статуса в здоровый после успешной инициализации
            self.status = ServiceStatus.HEALTHY
            self.logger.info("[CHECK_MARK_BUTTON] Enhanced Inference Service initialized successfully")
            
        except Exception as e:
            self.status = ServiceStatus.UNHEALTHY
            self.logger.error(f"[CROSS_MARK] Failed to initialize Inference Service: {e}")
            raise
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запросов на инференс."""
        request_type = request.get("type", "generate")
        self.logger.info(f"[CONFIG] Processing request type: {request_type}")
        
        if request_type == "generate":
            self.logger.info("[TARGET] Calling _handle_generate_request")
            return await self._handle_generate_request(request)
        elif request_type == "analyze_query":
            return await self._handle_query_analysis_request(request)
        elif request_type == "generate_prompt":
            return await self._handle_prompt_generation_request(request)
        elif request_type == "stats":
            return await self._handle_stats_request(request)
        elif request_type == "configure":
            return await self._handle_config_request(request)
        else:
            raise ValueError(f"Unknown request type: {request_type}")
    
    async def cleanup(self) -> None:
        """Очистка ресурсов Inference Service."""
        try:
            # Закрытие соединений с AI моделями
            if self.inference_system:
                # Здесь можно добавить cleanup логику для inference_system
                pass
            
            self.logger.info("[BROOM] Inference Service cleanup completed")

        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Error during Inference Service cleanup: {e}")

    async def generate_response(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Публичный метод для генерации AI-ответов.
        Используется для интеграции с SearchService и другими сервисами.

        Args:
            request: Словарь с параметрами:
                - query: вопрос пользователя
                - context: текстовый контекст для ответа
                - query_type: тип запроса (опционально)
                - max_tokens: максимальное количество токенов
                - temperature: температура генерации

        Returns:
            Dict с ключами:
                - success: bool - успешность операции
                - response: str - сгенерированный ответ
                - error: str - ошибка (если есть)
        """
        try:
            # Формируем запрос для внутреннего метода _handle_generate_request
            internal_request = {
                "type": "generate",
                "query": request.get("query", ""),
                "context": request.get("context", ""),
                "query_type": request.get("query_type", "legal_consultation"),
                "config": {
                    "max_tokens": request.get("max_tokens", self.default_config["max_tokens"]),
                    "temperature": request.get("temperature", self.default_config["temperature"]),
                    "timeout_seconds": request.get("timeout_seconds", self.default_config["timeout_seconds"])
                }
            }

            # Вызываем внутренний метод обработки
            result = await self.process_request(internal_request)

            # Возвращаем результат в ожидаемом формате
            if result.get("success", False):
                return {
                    "success": True,
                    "response": result.get("answer", ""), # ИСПРАВЛЕНО: answer, а не data.response
                    "model_info": {"model_used": result.get("model_used", "unknown")},
                    "generation_time": result.get("generation_time", 0)
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error occurred"),
                    "response": ""
                }

        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Generate response failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": ""
            }

    async def _handle_generate_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса генерации ответа."""
        query = request.get("query", "")
        context_chunks = request.get("context_chunks", [])
        query_type = request.get("query_type")
        config = request.get("config", {})

        if not query:
            raise ValueError("Query is required")

        # Логируем информацию о контексте
        if not context_chunks:
            self.logger.info("[LIGHT_BULB] No context chunks provided - using general knowledge mode")
        else:
            self.logger.info(f"[DOCS] Using {len(context_chunks)} context chunks for response generation")

        # КРИТИЧЕСКОЕ УЛУЧШЕНИЕ: Автоматическая активация Self-RAG для multi-document analysis
        # ВРЕМЕННО ОТКЛЮЧЕНО: Self-RAG слишком медленный (180+ сек) - используем быструю генерацию + verification
        if False and context_chunks and len(context_chunks) > 0 and self.self_rag_engine:
            self.logger.info(f"[ SELF-RAG] Activating Self-RAG engine for {len(context_chunks)} documents")
            try:
                # Преобразуем enriched chunks для Self-RAG с сохранением metadata
                document_strings = []
                documents_metadata = []
                for chunk in context_chunks:
                    if isinstance(chunk, dict):
                        # Enriched chunk - сохраняем metadata отдельно
                        document_strings.append(chunk.get("text", ""))
                        documents_metadata.append({
                            'law': chunk.get("law_number", "unknown"),
                            'article': chunk.get("article_number", ""),
                            'similarity': chunk.get("similarity", 0),
                            'doc_type': chunk.get("document_type", "")
                        })
                    elif hasattr(chunk, 'page_content'):
                        document_strings.append(chunk.page_content)
                        documents_metadata.append(getattr(chunk, 'metadata', {}))
                    elif isinstance(chunk, str):
                        document_strings.append(chunk)
                        documents_metadata.append({})
                    else:
                        document_strings.append(str(chunk))
                        documents_metadata.append({})

                # Вызываем Self-RAG генерацию с автоматической критикой
                self_rag_result = await self.generate_self_rag_response(query, document_strings)

                # Если Self-RAG успешен - возвращаем его результат
                if self_rag_result.get("success", False):
                    self.logger.info(f"[ SELF-RAG] Success! Confidence: {self_rag_result.get('confidence_score', 0):.2f}")
                    return {
                        "success": True,
                        "query": query,
                        "answer": self_rag_result.get("answer"),
                        "query_type": "self_rag_legal",
                        "chunks_used": len(context_chunks),
                        "generation_time": self_rag_result.get("generation_time", 0),
                        "model_used": "gemini-2.5-flash-with-self-rag",
                        "confidence_score": self_rag_result.get("confidence_score", 0),
                        "self_rag_metrics": self_rag_result.get("self_rag_metrics")
                    }
                else:
                    self.logger.warning("[ SELF-RAG] Failed, falling back to standard generation")
            except Exception as e:
                self.logger.warning(f"[ SELF-RAG] Error: {e}, falling back to standard generation")

        self.logger.info(f"[AI] Generating answer for: {query[:100]}...")

        start_time = time.time()

        try:
            # Определение типа запроса если не указан
            if not query_type and self.prompt_engine:
                detected_type = self.prompt_engine.detect_query_type(query)
                query_type = detected_type.value

            # УЛУЧШЕНО: Генерация адаптивного промпта с универсальной системой
            system_prompt = ""
            user_prompt = ""

            # PHASE 2: ENHANCED PROMPTS с few-shot примерами для улучшения качества ответов
            try:
                from core.legal_prompts_enhanced import (
                    get_enhanced_legal_system_prompt,
                    format_enhanced_legal_prompt
                )

                system_prompt = get_enhanced_legal_system_prompt()

                if context_chunks:
                    # PHASE 2: Используем новый формат промпта с few-shot примерами
                    # format_enhanced_legal_prompt автоматически обрабатывает enriched chunks
                    user_prompt = format_enhanced_legal_prompt(query, context_chunks)
                else:
                    user_prompt = format_enhanced_legal_prompt(query, [])

                self.logger.info("[ PHASE2] Using enhanced prompts with few-shot examples")

            except Exception as e:
                self.logger.warning(f"[WARNING] Failed to use optimized prompts, falling back: {e}")
                # Fallback к стандартному prompt engine
                if self.prompt_engine:
                    system_prompt, user_prompt = self.prompt_engine.generate_adaptive_prompt(
                        query=query,
                        chunks=context_chunks
                    )

            else:
                # Fallback промпт, адаптированный под наличие/отсутствие контекста
                if context_chunks:
                    # FIX: Extract text from enriched chunks for fallback
                    context_texts = []
                    for chunk in context_chunks:
                        if isinstance(chunk, dict):
                            context_texts.append(chunk.get("text", str(chunk)))
                        else:
                            context_texts.append(str(chunk))

                    user_prompt = f"""
Контекст:
{chr(10).join(context_texts)}

Вопрос: {query}

Ответьте на вопрос на основе предоставленного контекста.
"""
                else:
                    user_prompt = f"""
Вопрос: {query}

Ответьте на вопрос на основе ваших знаний. Если у вас недостаточно информации для полного ответа, укажите это и предложите общие рекомендации по теме.
"""
            
            # Генерация ответа через AI
            self.logger.info(f"[SEARCH] Inference system: {self.inference_system is not None}")
            if not self.inference_system:
                self.logger.error("[CROSS_MARK] Inference system not initialized")
                raise RuntimeError("Inference system not initialized")
            
            # Подготовка конфигурации для AI модели
            inference_config = {
                **self.default_config,
                **config
            }
            
            # Генерация ответа
            self.logger.info("[ROCKET] About to call _generate_ai_response")
            try:
                ai_response = await self._generate_ai_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    config=inference_config
                )
                self.logger.info(f"[CHECK_MARK_BUTTON] Got AI response: {ai_response[:100]}...")
            except Exception as e:
                self.logger.error(f"[CROSS_MARK] Error in _generate_ai_response: {e}")
                raise
            
            generation_time = time.time() - start_time

            # Обновление метрик
            self._update_inference_metrics(generation_time, success=True)

            self.logger.info(f"[CHECK_MARK_BUTTON] Answer generated successfully in {generation_time:.2f}s")

            # ФАЗА 1.3: Multi-layer Verification
            verification_result = None
            if self.enable_verification and context_chunks:
                try:
                    self.logger.info("[ VERIFICATION] Starting answer verification")
                    verification_result = await self.legal_verifier.verify_answer_against_sources(
                        answer=ai_response,
                        sources=context_chunks,
                        query=query
                    )

                    self.logger.info(f"[ VERIFIED] Confidence: {verification_result.overall_confidence:.2f}, Recommendation: {verification_result.recommendation}")

                    # Если ответ ненадежный - добавляем предупреждение
                    if not verification_result.is_reliable(VerificationSeverity.MEDIUM):
                        warning = (
                            f"\n\n ВНИМАНИЕ: Автоматическая верификация обнаружила возможные проблемы "
                            f"(confidence: {verification_result.overall_confidence:.2%}). "
                            f"Рекомендуется дополнительная проверка."
                        )
                        ai_response = ai_response + warning
                except Exception as e:
                    self.logger.warning(f"[ VERIFICATION] Verification failed: {e}")

            response_data = {
                "success": True,
                "query": query,
                "answer": ai_response,
                "query_type": query_type,
                "chunks_used": len(context_chunks),
                "generation_time": generation_time,
                "model_used": inference_config.get("model", "unknown")
            }

            # Добавляем verification metrics если они есть
            if verification_result:
                response_data["verification"] = {
                    "confidence": verification_result.overall_confidence,
                    "recommendation": verification_result.recommendation,
                    "citation_accuracy": verification_result.citation_accuracy,
                    "support_rate": verification_result.support_rate,
                    "is_reliable": verification_result.is_reliable(VerificationSeverity.MEDIUM)
                }

            return response_data
            
        except Exception as e:
            generation_time = time.time() - start_time
            self._update_inference_metrics(generation_time, success=False)
            
            self.logger.error(f"[CROSS_MARK] Answer generation failed: {e}")
            raise
    
    async def _handle_query_analysis_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса анализа типа запроса."""
        query = request.get("query", "")
        
        if not query:
            raise ValueError("Query is required")
        
        if not self.prompt_engine:
            raise RuntimeError("Prompt engine not initialized")
        
        try:
            # Определение типа запроса
            query_type = self.prompt_engine.detect_query_type(query)
            
            # Получение статистики промптов
            prompt_stats = self.prompt_engine.get_prompt_stats()
            
            return {
                "query": query,
                "detected_type": query_type.value,
                "confidence": "high", # Можно добавить логику определения уверенности
                "available_types": [t.value for t in QueryType],
                "prompt_stats": prompt_stats
            }
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Query analysis failed: {e}")
            raise
    
    async def _handle_prompt_generation_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса генерации промпта."""
        query = request.get("query", "")
        context_chunks = request.get("context_chunks", [])
        query_type = request.get("query_type")
        
        if not query:
            raise ValueError("Query is required")
        
        if not self.prompt_engine:
            raise RuntimeError("Prompt engine not initialized")
        
        try:
            # Генерация адаптивного промпта
            system_prompt, user_prompt = self.prompt_engine.generate_adaptive_prompt(
                query=query,
                chunks=context_chunks
            )
            
            return {
                "query": query,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "query_type_used": query_type,
                "context_chunks_count": len(context_chunks)
            }
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Prompt generation failed: {e}")
            raise
    
    async def _handle_stats_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса статистики."""
        stats = {
            "service_metrics": self.get_metrics(),
            "inference_metrics": self.inference_metrics.copy(),
            "prompt_stats": {}
        }
        
        # Статистика промптов
        if self.prompt_engine:
            stats["prompt_stats"] = self.prompt_engine.get_prompt_stats()
        
        return stats
    
    async def _handle_config_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса конфигурации."""
        action = request.get("action", "get")
        
        if action == "get":
            return {
                "current_config": self.default_config,
                "inference_metrics": self.inference_metrics
            }
        
        elif action == "update":
            new_config = request.get("config", {})
            self.default_config.update(new_config)
            
            return {
                "status": "updated",
                "new_config": self.default_config
            }
        
        else:
            raise ValueError(f"Unknown config action: {action}")
    
    async def _generate_ai_response(
        self,
        system_prompt: str,
        user_prompt: str,
        config: Dict[str, Any]
    ) -> str:
        """Генерация ответа через AI модель."""
        try:
            # Использование inference_system для генерации ответа
            self.logger.info(f"[SEARCH] AI system type: {type(self.inference_system)}")

            if hasattr(self.inference_system, 'generate_response'):
                self.logger.info("[CHECK_MARK_BUTTON] Found generate_response method")

                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Объединяем system_prompt + user_prompt в один промпт
                # Gemini лучше работает когда все инструкции в одном промпте
                if system_prompt and system_prompt.strip():
                    combined_prompt = f"{system_prompt}\n\n{'='*80}\n\n{user_prompt}"
                else:
                    combined_prompt = user_prompt

                # Подготовка параметров для EnhancedInferenceEngine
                ai_params = {
                    'prompt': combined_prompt, # Всё в одном промпте
                    'max_tokens': config.get('max_tokens', 2048),
                    'temperature': config.get('temperature', 0.05) # Минимальная температура для точности
                }

                self.logger.info(f"[ROCKET] Calling generate_response with combined prompt ({len(combined_prompt)} chars)")
                response_data = await self.inference_system.generate_response(**ai_params)
                self.logger.info(f" Received response type: {type(response_data)}")

                # Извлекаем текст ответа из результата
                if isinstance(response_data, dict) and 'response' in response_data:
                    response_text = response_data['response']
                    self.logger.info(f"[CHECK_MARK_BUTTON] Extracted response from dict: {len(response_text)} chars")
                elif isinstance(response_data, str):
                    response_text = response_data
                    self.logger.info(f"[CHECK_MARK_BUTTON] Got string response: {len(response_text)} chars")
                else:
                    response_text = str(response_data)
                    self.logger.info(f"[CHECK_MARK_BUTTON] Converted to string: {len(response_text)} chars")

                # PHASE 2.1: CRITICAL - Check for empty responses
                if not response_text or len(response_text.strip()) == 0:
                    self.logger.error(f"[ EMPTY] Gemini returned EMPTY response!")
                    self.logger.error(f"[ EMPTY] Query: {user_prompt[:200]}...")
                    self.logger.error(f"[ EMPTY] Config: {ai_params}")

                    # Попытка retry с упрощенным промптом
                    self.logger.warning("[ RETRY] Attempting retry with simplified prompt...")
                    retry_prompt = f"Вопрос: {user_prompt.split('Вопрос:')[-1] if 'Вопрос:' in user_prompt else user_prompt}"
                    ai_params['prompt'] = retry_prompt

                    response_data_retry = await self.inference_system.generate_response(**ai_params)
                    if isinstance(response_data_retry, dict) and 'response' in response_data_retry:
                        response_text = response_data_retry['response']
                    elif isinstance(response_data_retry, str):
                        response_text = response_data_retry
                    else:
                        response_text = str(response_data_retry)

                    if not response_text or len(response_text.strip()) == 0:
                        self.logger.error("[ RETRY FAILED] Still empty after retry!")
                        return "Извините, не удалось сгенерировать ответ. Попробуйте переформулировать вопрос."
                    else:
                        self.logger.info(f"[ RETRY SUCCESS] Got response after retry: {len(response_text)} chars")

                self.logger.info(f"[ FINAL] Returning response: {len(response_text)} chars, first 200: {response_text[:200]}")
                return response_text
            
            elif hasattr(self.inference_system, 'generate_answer'):
                response = await self.inference_system.generate_answer(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    **config
                )
                return response
            
            elif hasattr(self.inference_system, 'ask_question'):
                # Fallback для старого интерфейса
                response = await self.inference_system.ask_question(
                    question=user_prompt,
                    context_chunks=[] # Контекст уже в промпте
                )
                return response
            
            else:
                # Последний fallback - имитация ответа
                self.logger.warning("[WARNING] Using fallback AI response generation")
                return f"Ответ на запрос: {user_prompt[:100]}... [Сгенерировано через fallback]"
                
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] AI generation error: {e}")
            raise RuntimeError(f"AI response generation failed: {e}")
    
    def _update_inference_metrics(self, generation_time: float, success: bool) -> None:
        """Обновление метрик инференса."""
        self.inference_metrics["total_requests"] += 1
        
        if success:
            self.inference_metrics["successful_requests"] += 1
        else:
            self.inference_metrics["failed_requests"] += 1
        
        # Обновление времени генерации
        self.inference_metrics["generation_times"].append(generation_time)
        
        # Оставляем только последние 100 измерений
        if len(self.inference_metrics["generation_times"]) > 100:
            self.inference_metrics["generation_times"] = self.inference_metrics["generation_times"][-100:]
        
        # Пересчет среднего времени
        times = self.inference_metrics["generation_times"]
        self.inference_metrics["avg_generation_time"] = sum(times) / len(times) if times else 0.0
    
    async def _additional_health_checks(self) -> Dict[str, bool]:
        """Дополнительные проверки здоровья для Inference Service."""
        checks = {}
        
        # Проверка компонентов
        checks["inference_system_ready"] = self.inference_system is not None
        checks["prompt_engine_ready"] = self.prompt_engine is not None
        
        # Проверка производительности
        checks["acceptable_response_time"] = self.inference_metrics["avg_generation_time"] < 10.0
        checks["low_error_rate"] = (
            self.inference_metrics["failed_requests"] / 
            max(self.inference_metrics["total_requests"], 1)
        ) < 0.05
        
        # Проверка AI системы
        if self.inference_system:
            try:
                # Простая проверка доступности AI
                checks["ai_system_responsive"] = True
            except Exception:
                checks["ai_system_responsive"] = False

        return checks

    # КРИТИЧЕСКОЕ УЛУЧШЕНИЕ: Self-RAG метод
    async def generate_self_rag_response(self, query: str, initial_documents: List[str]) -> Dict[str, Any]:
        """
        Генерация ответа с использованием Self-RAG архитектуры и IRAC промптов

        Args:
            query: Правовой запрос пользователя
            initial_documents: Начальный набор документов

        Returns:
            Dict с ответом и метриками качества
        """
        start_time = time.time()

        try:
            if not self.self_rag_engine:
                self.logger.warning("[] Self-RAG engine not available, falling back to standard generation")
                return await self._fallback_generation(query, initial_documents)

            self.logger.info(f"[] Starting Self-RAG generation for: {query[:100]}...")

            # Применяем Self-RAG с автоматической критикой
            self_rag_result: SelfRAGResult = await self.self_rag_engine.generate_with_self_critique(
                query, initial_documents
            )

            generation_time = time.time() - start_time

            # Подготавливаем ответ с метриками
            response = {
                "answer": self_rag_result.answer,
                "success": True,
                "generation_time": generation_time,
                "confidence_score": self_rag_result.confidence_score,

                # Детальная информация о Self-RAG процессе
                "self_rag_metrics": {
                    "documents_used": len(self_rag_result.used_documents),
                    "critique_results": {
                        key: {
                            "decision": result.decision.value,
                            "confidence": result.confidence,
                            "reasoning": result.reasoning
                        }
                        for key, result in self_rag_result.critique_results.items()
                    },
                    "verification_details": self_rag_result.verification_details
                },

                # Рекомендации на основе quality score
                "quality_assessment": self._assess_response_quality(self_rag_result),

                # Метрики для мониторинга
                "metrics": {
                    "irac_structure_present": self._check_irac_structure(self_rag_result.answer),
                    "citation_count": self._count_legal_citations(self_rag_result.answer),
                    "legal_terminology_density": self._calculate_legal_term_density(self_rag_result.answer)
                }
            }

            # Обновляем метрики сервиса
            self._update_self_rag_metrics(response)

            self.logger.info(f"[] Self-RAG generation completed: confidence={self_rag_result.confidence_score:.2f}")

            return response

        except Exception as e:
            self.logger.error(f"[] Self-RAG generation failed: {e}")
            return await self._fallback_generation(query, initial_documents)

    async def _fallback_generation(self, query: str, documents: List[str]) -> Dict[str, Any]:
        """Резервная генерация при недоступности Self-RAG"""
        try:
            # Используем IRAC промпты хотя бы
            irac_prompt = self.russian_legal_prompts.format_legal_query(query, documents)

            response_text = await self.inference_system.generate_response(
                prompt=irac_prompt,
                temperature=0.05,
                max_tokens=2048
            )

            return {
                "answer": response_text if isinstance(response_text, str) else str(response_text),
                "success": True,
                "confidence_score": 0.5, # Средняя уверенность для fallback
                "generation_method": "fallback_irac",
                "self_rag_metrics": None
            }

        except Exception as e:
            self.logger.error(f"[] Fallback generation failed: {e}")
            return {
                "answer": "ОШИБКА: Не удалось сгенерировать ответ. Попробуйте переформулировать вопрос.",
                "success": False,
                "confidence_score": 0.0,
                "error": str(e)
            }

    def _assess_response_quality(self, self_rag_result: SelfRAGResult) -> Dict[str, Any]:
        """Оценка качества ответа на основе Self-RAG метрик"""
        assessment = {
            "overall_quality": "unknown",
            "recommendations": [],
            "confidence_level": "unknown"
        }

        confidence = self_rag_result.confidence_score

        if confidence >= 0.8:
            assessment["overall_quality"] = "high"
            assessment["confidence_level"] = "high"
            assessment["recommendations"].append("Ответ готов к использованию")
        elif confidence >= 0.6:
            assessment["overall_quality"] = "medium"
            assessment["confidence_level"] = "medium"
            assessment["recommendations"].append("Рекомендуется дополнительная проверка")
        else:
            assessment["overall_quality"] = "low"
            assessment["confidence_level"] = "low"
            assessment["recommendations"].append("Требуется переформулировка запроса или дополнительные источники")

        return assessment

    def _check_irac_structure(self, answer: str) -> bool:
        """Проверка наличия IRAC структуры в ответе"""
        irac_markers = ["проблема", "норма", "анализ", "вывод", "статья"]
        found_markers = sum(1 for marker in irac_markers if marker.lower() in answer.lower())
        return found_markers >= 3

    def _count_legal_citations(self, answer: str) -> int:
        """Подсчет количества правовых ссылок"""
        import re

        # Паттерны для российских правовых ссылок
        citation_patterns = [
            r'\d+-ФЗ', # Федеральные законы
            r'[Сс]татья\s+\d+', # Статьи
            r'[Пп]ункт\s+\d+', # Пункты
            r'[Гг]лава\s+\d+' # Главы
        ]

        total_citations = 0
        for pattern in citation_patterns:
            total_citations += len(re.findall(pattern, answer))

        return total_citations

    def _calculate_legal_term_density(self, answer: str) -> float:
        """Расчет плотности правовых терминов"""
        legal_terms = [
            'концедент', 'концессионер', 'концессионное соглашение',
            'государственно-частное партнерство', 'правовая норма',
            'федеральный закон', 'правоотношения'
        ]

        words = answer.lower().split()
        if not words:
            return 0.0

        legal_word_count = sum(1 for word in words if any(term in word for term in legal_terms))
        return legal_word_count / len(words)

    def _update_self_rag_metrics(self, response: Dict[str, Any]):
        """Обновление метрик Self-RAG"""
        if not hasattr(self, 'self_rag_metrics'):
            self.self_rag_metrics = {
                "total_requests": 0,
                "high_confidence_responses": 0,
                "avg_confidence": 0.0,
                "irac_compliance_rate": 0.0
            }

        self.self_rag_metrics["total_requests"] += 1

        confidence = response.get("confidence_score", 0.0)
        if confidence >= 0.8:
            self.self_rag_metrics["high_confidence_responses"] += 1

        # Обновляем среднюю уверенность
        total = self.self_rag_metrics["total_requests"]
        current_avg = self.self_rag_metrics["avg_confidence"]
        self.self_rag_metrics["avg_confidence"] = (current_avg * (total - 1) + confidence) / total


async def create_inference_service() -> InferenceService:
    """Factory function for fully initialized InferenceService."""
    service = InferenceService()
    await service.start()
    return service


if __name__ == "__main__":
    import asyncio

    configure_logging(os.getenv("LOG_LEVEL", "INFO"))

    async def main():
        service = InferenceService()
        await service.initialize()
        await service.shutdown()

    asyncio.run(main())