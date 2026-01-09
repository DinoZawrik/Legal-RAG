"""
Улучшенный правовой ассистент - главный интеграционный модуль.
Объединяет все компоненты для создания интеллектуальной системы правовых консультаций.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio
import json

# Импорт всех созданных компонентов
from .legal_ontology import LegalOntology, DocumentType
from .smart_query_classifier import SmartQueryClassifier, QueryType, UserExpertiseLevel, QueryAnalysis
from .legal_chunker import LegalDocumentChunker, LegalChunk
from .hybrid_search import HybridLegalSearch, SearchResult
from .semantic_history import SemanticHistoryCompressor, CompressedMessage, ConversationSummary
from .adaptive_prompts import AdaptivePromptSystem, ResponseStyle
from .legal_inference import LegalInferenceEngine, LegalRule, InferenceResult
from .enhanced_response_generator import EnhancedResponseGenerator, StructuredResponse, ResponseQuality
from .quality_validation import QualityValidator, ValidationReport

logger = logging.getLogger(__name__)

@dataclass
class LegalConsultationRequest:
    """Запрос на правовую консультацию"""
    query: str
    user_id: str
    user_expertise: UserExpertiseLevel = UserExpertiseLevel.INTERMEDIATE

    # Дополнительный контекст
    conversation_history: Optional[List[Dict[str, Any]]] = None
    specific_requirements: Optional[Dict[str, Any]] = None
    priority_documents: Optional[List[str]] = None

    # Метаданные запроса
    timestamp: datetime = None
    session_id: Optional[str] = None
    request_type: str = "consultation"

@dataclass
class LegalConsultationResponse:
    """Полный ответ системы правовых консультаций"""
    request_id: str
    structured_response: StructuredResponse
    validation_report: ValidationReport

    # Метаданные обработки
    processing_time: float
    components_used: List[str]
    confidence_score: float

    # Дополнительные результаты
    search_metadata: Dict[str, Any]
    inference_metadata: Dict[str, Any]
    quality_insights: Dict[str, Any]

class EnhancedLegalAssistant:
    """
    Улучшенный правовой ассистент - интеграционная система.
    Обеспечивает интеллектуальные правовые консультации с использованием всех компонентов.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Инициализация улучшенного правового ассистента.

        Args:
            config: Конфигурация системы
        """
        self.config = config or self._get_default_config()

        # Инициализация всех компонентов
        logger.info("Инициализация улучшенного правового ассистента...")

        try:
            # Базовые компоненты (обязательные)
            self.legal_ontology = LegalOntology()
            self.query_classifier = SmartQueryClassifier()
            self.legal_chunker = LegalDocumentChunker()

            # Поиск и анализ (опциональные)
            try:
                self.hybrid_search = HybridLegalSearch()
            except Exception as e:
                logger.warning(f"HybridSearch инициализация пропущена: {e}")
                self.hybrid_search = None

            try:
                self.semantic_history = SemanticHistoryCompressor()
            except Exception as e:
                logger.warning(f"SemanticHistory инициализация пропущена: {e}")
                self.semantic_history = None

            # Генерация и валидация
            self.adaptive_prompts = AdaptivePromptSystem()

            try:
                self.inference_engine = LegalInferenceEngine()
            except Exception as e:
                logger.warning(f"LegalInference инициализация пропущена: {e}")
                self.inference_engine = None

            self.response_generator = EnhancedResponseGenerator()
            self.quality_validator = QualityValidator()

            # Статистика использования
            self.usage_stats = {
                'total_consultations': 0,
                'successful_consultations': 0,
                'average_quality_score': 0.0,
                'component_usage': {},
                'error_count': 0
            }

            logger.info("Enhanced Legal Assistant инициализирован")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            raise

    def _get_default_config(self) -> Dict[str, Any]:
        """Получает конфигурацию по умолчанию"""
        return {
            'enable_quality_validation': True,
            'enable_inference_engine': True,
            'enable_semantic_compression': True,
            'max_search_results': 10,
            'quality_threshold': 0.7,
            'response_timeout': 30.0,
            'cache_responses': True,
            'log_detailed_metrics': True
        }

    async def process_legal_consultation(self, request: LegalConsultationRequest) -> LegalConsultationResponse:
        """
        Основной метод обработки правовой консультации.

        Args:
            request: Запрос на консультацию

        Returns:
            Полный ответ с правовой консультацией
        """
        start_time = datetime.now()
        request_id = f"req_{int(start_time.timestamp())}_{hash(request.query) % 10000}"

        try:
            logger.info(f"🚀 Начало обработки консультации {request_id}")

            # 1. ФАЗА АНАЛИЗА ЗАПРОСА
            logger.info("📋 Фаза 1: Анализ запроса")
            query_analysis = await self._analyze_query(request)

            # 2. ФАЗА ПОИСКА ИНФОРМАЦИИ
            logger.info("🔍 Фаза 2: Поиск релевантной информации")
            search_results, search_metadata = await self._search_legal_information(
                request, query_analysis
            )

            # 3. ФАЗА ОБРАБОТКИ ИСТОРИИ
            logger.info("💭 Фаза 3: Обработка истории разговора")
            conversation_context = await self._process_conversation_history(request)

            # 4. ФАЗА ПРАВОВОГО АНАЛИЗА
            logger.info("⚖️ Фаза 4: Правовой анализ и выводы")
            legal_analysis, inference_metadata = await self._perform_legal_analysis(
                request, query_analysis, search_results
            )

            # 5. ФАЗА ГЕНЕРАЦИИ ОТВЕТА
            logger.info("📝 Фаза 5: Генерация структурированного ответа")
            structured_response = await self._generate_structured_response(
                request, query_analysis, search_results, conversation_context, legal_analysis
            )

            # 6. ФАЗА ВАЛИДАЦИИ КАЧЕСТВА
            logger.info("✅ Фаза 6: Валидация качества")
            validation_report = await self._validate_response_quality(
                structured_response, search_results, request.query
            )

            # 7. ФОРМИРОВАНИЕ ИТОГОВОГО ОТВЕТА
            processing_time = (datetime.now() - start_time).total_seconds()

            response = LegalConsultationResponse(
                request_id=request_id,
                structured_response=structured_response,
                validation_report=validation_report,
                processing_time=processing_time,
                components_used=self._get_used_components(),
                confidence_score=self._calculate_confidence_score(structured_response, validation_report),
                search_metadata=search_metadata,
                inference_metadata=inference_metadata,
                quality_insights=self._generate_quality_insights(validation_report)
            )

            # Обновление статистики
            await self._update_usage_stats(response)

            logger.info(f"✅ Консультация {request_id} завершена за {processing_time:.2f}с "
                       f"(качество: {validation_report.quality_grade.value})")

            return response

        except Exception as e:
            logger.error(f"❌ Ошибка при обработке консультации {request_id}: {e}")
            self.usage_stats['error_count'] += 1
            return await self._create_error_response(request_id, str(e), start_time)

    async def _analyze_query(self, request: LegalConsultationRequest) -> QueryAnalysis:
        """Анализирует запрос пользователя"""
        try:
            analysis = self.query_classifier.analyze_query(
                request.query,
                request.conversation_history
            )

            # Дополнительная информация из онтологии
            try:
                # Используем доступный метод для получения правовой области
                legal_domain, confidence = self.legal_ontology.get_legal_domain(request.query)
                if confidence > 0.5 and not analysis.legal_area:
                    analysis.legal_area = legal_domain.value
            except Exception as e:
                logger.warning(f"Ошибка получения правовой области: {e}")

            return analysis

        except Exception as e:
            logger.error(f"Ошибка анализа запроса: {e}")
            # Fallback анализ
            return QueryAnalysis(
                query_type=QueryType.LEGAL_CONSULTATION,
                user_expertise=request.user_expertise,
                complexity="medium",
                legal_area="Общие правовые вопросы",
                key_concepts=[],
                intent_confidence=0.5
            )

    async def _search_legal_information(self, request: LegalConsultationRequest,
                                       query_analysis: QueryAnalysis) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Выполняет поиск релевантной правовой информации"""
        try:
            # Используем гибридный поиск
            search_results = await self.hybrid_search.search_with_legal_context(
                query=request.query,
                user_history=request.conversation_history,
                max_results=self.config.get('max_search_results', 10),
                query_analysis=query_analysis
            )

            # Преобразуем результаты в нужный формат
            formatted_results = []
            for result in search_results:
                formatted_result = {
                    'content': result.content,
                    'metadata': {
                        'document_title': result.metadata.get('document_title', 'Неизвестный документ'),
                        'document_type': result.metadata.get('document_type', ''),
                        'article_number': result.metadata.get('article_number', ''),
                        'adoption_date': result.metadata.get('adoption_date', ''),
                        'legal_concepts': result.metadata.get('legal_concepts', [])
                    },
                    'score': result.relevance_score,
                    'search_type': result.search_type
                }
                formatted_results.append(formatted_result)

            # Метаданные поиска
            search_metadata = {
                'total_results': len(formatted_results),
                'search_types_used': list(set(r.search_type for r in search_results)),
                'average_relevance': sum(r.relevance_score for r in search_results) / len(search_results) if search_results else 0,
                'query_analysis': asdict(query_analysis)
            }

            return formatted_results, search_metadata

        except Exception as e:
            logger.error(f"Ошибка поиска информации: {e}")
            return [], {'error': str(e), 'total_results': 0}

    async def _process_conversation_history(self, request: LegalConsultationRequest) -> Optional[Dict[str, Any]]:
        """Обрабатывает историю разговора"""
        if not request.conversation_history or not self.config.get('enable_semantic_compression', True):
            return None

        try:
            compressed_messages, conversation_summary = await self.semantic_compressor.compress_conversation_history(
                request.conversation_history,
                max_compressed_messages=10
            )

            return {
                'compressed_messages': compressed_messages,
                'conversation_summary': conversation_summary,
                'context_string': self.semantic_compressor.to_context_string(
                    compressed_messages, conversation_summary
                )
            }

        except Exception as e:
            logger.error(f"Ошибка обработки истории: {e}")
            return None

    async def _perform_legal_analysis(self, request: LegalConsultationRequest,
                                    query_analysis: QueryAnalysis,
                                    search_results: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Выполняет правовой анализ и выводы"""
        if not self.config.get('enable_inference_engine', True):
            return {}, {'inference_disabled': True}

        try:
            # Извлечение правовых норм из результатов поиска
            legal_rules = []
            for result in search_results:
                rule = self.inference_engine.parse_legal_rule(
                    result['content'],
                    result['metadata']
                )
                if rule:
                    legal_rules.append(rule)

            # Извлечение фактов из запроса
            facts = self._extract_facts_from_query(request.query)

            # Правовой анализ
            legal_reasoning = self.inference_engine.generate_legal_reasoning(
                request.query, facts, legal_rules, request.user_expertise
            )

            # Метаданные анализа
            inference_metadata = {
                'rules_found': len(legal_rules),
                'facts_extracted': len(facts),
                'inferences_count': len(legal_reasoning.get('analysis', {}).get('inferences', {}).get('deductive', [])),
                'conflicts_found': len(legal_reasoning.get('analysis', {}).get('conflicts', [])),
                'gaps_identified': len(legal_reasoning.get('analysis', {}).get('gaps', []))
            }

            return legal_reasoning, inference_metadata

        except Exception as e:
            logger.error(f"Ошибка правового анализа: {e}")
            return {}, {'error': str(e)}

    async def _generate_structured_response(self, request: LegalConsultationRequest,
                                          query_analysis: QueryAnalysis,
                                          search_results: List[Dict[str, Any]],
                                          conversation_context: Optional[Dict[str, Any]],
                                          legal_analysis: Dict[str, Any]) -> StructuredResponse:
        """Генерирует структурированный ответ"""
        try:
            # Подготовка данных для генератора ответов
            conversation_summary = None
            compressed_messages = []

            if conversation_context:
                conversation_summary = conversation_context.get('conversation_summary')
                compressed_messages = conversation_context.get('compressed_messages', [])

            # Генерация ответа
            structured_response = await self.response_generator.generate_enhanced_response(
                user_query=request.query,
                search_results=search_results,
                user_expertise=request.user_expertise,
                conversation_history=request.conversation_history,
                additional_context={
                    'query_analysis': query_analysis,
                    'legal_analysis': legal_analysis,
                    'conversation_summary': conversation_summary
                }
            )

            return structured_response

        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            return await self._create_fallback_structured_response(request, search_results)

    async def _validate_response_quality(self, response: StructuredResponse,
                                       search_results: List[Dict[str, Any]],
                                       original_query: str) -> ValidationReport:
        """Валидирует качество ответа"""
        if not self.config.get('enable_quality_validation', True):
            return self._create_minimal_validation_report(response.response_id)

        try:
            validation_report = await self.quality_validator.validate_response(
                response, search_results, original_query
            )
            return validation_report

        except Exception as e:
            logger.error(f"Ошибка валидации качества: {e}")
            return self._create_minimal_validation_report(response.response_id, str(e))

    def _extract_facts_from_query(self, query: str) -> List[str]:
        """Извлекает фактические обстоятельства из запроса"""
        # Используем метод из response_generator
        return self.response_generator._extract_facts_from_query(query)

    def _get_used_components(self) -> List[str]:
        """Получает список использованных компонентов"""
        components = ['legal_ontology', 'query_classifier', 'response_generator']

        if self.config.get('enable_inference_engine', True):
            components.append('inference_engine')
        if self.config.get('enable_semantic_compression', True):
            components.append('semantic_compressor')
        if self.config.get('enable_quality_validation', True):
            components.append('quality_validator')

        components.extend(['hybrid_search', 'adaptive_prompts'])

        return components

    def _calculate_confidence_score(self, response: StructuredResponse,
                                   validation_report: ValidationReport) -> float:
        """Вычисляет общую уверенность в ответе"""
        factors = []

        # Качество ответа
        factors.append(validation_report.overall_score)

        # Количество источников
        source_score = min(len(response.sources) / 3, 1.0)  # Максимум за 3 источника
        factors.append(source_score)

        # Наличие инференсов
        if response.inferences:
            avg_confidence = sum(inf.confidence for inf in response.inferences) / len(response.inferences)
            factors.append(avg_confidence)
        else:
            factors.append(0.5)  # Средняя уверенность без инференсов

        # Критические проблемы снижают уверенность
        if validation_report.critical_issues > 0:
            factors.append(0.3)
        else:
            factors.append(1.0)

        return sum(factors) / len(factors)

    def _generate_quality_insights(self, validation_report: ValidationReport) -> Dict[str, Any]:
        """Генерирует инсайты о качестве"""
        insights = {
            'overall_assessment': validation_report.quality_grade.value,
            'strengths': [],
            'improvement_areas': [],
            'risk_level': 'low'
        }

        # Сильные стороны
        if validation_report.overall_score >= 0.9:
            insights['strengths'].append('Высочайшее качество анализа')
        if validation_report.critical_issues == 0:
            insights['strengths'].append('Отсутствие критических ошибок')
        if validation_report.auto_fixable_issues > 0:
            insights['strengths'].append('Большинство проблем автоисправимы')

        # Области улучшения
        if validation_report.critical_issues > 0:
            insights['improvement_areas'].append('Устранение критических ошибок')
            insights['risk_level'] = 'high'
        elif validation_report.total_issues > 5:
            insights['improvement_areas'].append('Общее улучшение качества')
            insights['risk_level'] = 'medium'

        insights['priority_actions'] = validation_report.priority_fixes[:3]

        return insights

    async def _update_usage_stats(self, response: LegalConsultationResponse):
        """Обновляет статистику использования"""
        self.usage_stats['total_consultations'] += 1

        if response.validation_report.quality_grade in [ResponseQuality.GOOD, ResponseQuality.EXCELLENT]:
            self.usage_stats['successful_consultations'] += 1

        # Обновляем среднее качество
        current_avg = self.usage_stats['average_quality_score']
        total = self.usage_stats['total_consultations']
        new_score = response.validation_report.overall_score

        self.usage_stats['average_quality_score'] = (current_avg * (total - 1) + new_score) / total

        # Статистика компонентов
        for component in response.components_used:
            self.usage_stats['component_usage'][component] = \
                self.usage_stats['component_usage'].get(component, 0) + 1

    async def _create_error_response(self, request_id: str, error_message: str,
                                   start_time: datetime) -> LegalConsultationResponse:
        """Создает ответ об ошибке"""
        processing_time = (datetime.now() - start_time).total_seconds()

        # Минимальный структурированный ответ
        error_response = StructuredResponse(
            query="ERROR",
            response_id=f"error_{request_id}",
            timestamp=datetime.now(),
            user_expertise=UserExpertiseLevel.INTERMEDIATE
        )

        error_response.sections = {
            'summary': f"Извините, произошла техническая ошибка: {error_message}",
            'recommendations': "Попробуйте перефразировать вопрос или обратитесь к администратору."
        }
        error_response.warnings = ["Системная ошибка"]

        # Минимальный отчет валидации
        validation_report = ValidationReport(
            response_id=error_response.response_id,
            timestamp=datetime.now(),
            overall_score=0.0,
            quality_grade=ResponseQuality.POOR,
            total_issues=1,
            critical_issues=1
        )

        return LegalConsultationResponse(
            request_id=request_id,
            structured_response=error_response,
            validation_report=validation_report,
            processing_time=processing_time,
            components_used=['error_handler'],
            confidence_score=0.0,
            search_metadata={'error': error_message},
            inference_metadata={'error': error_message},
            quality_insights={'overall_assessment': 'error', 'risk_level': 'high'}
        )

    async def _create_fallback_structured_response(self, request: LegalConsultationRequest,
                                                 search_results: List[Dict[str, Any]]) -> StructuredResponse:
        """Создает базовый ответ в случае ошибки генерации"""
        response = StructuredResponse(
            query=request.query,
            response_id=f"fallback_{int(datetime.now().timestamp())}",
            timestamp=datetime.now(),
            user_expertise=request.user_expertise
        )

        # Базовые секции
        response.sections = {
            'summary': "Извините, возникла ошибка при генерации подробного ответа.",
            'legal_basis': "Рекомендуется обратиться к специалисту.",
            'sources': self._format_sources_fallback(search_results)
        }

        response.warnings = ["Упрощенный режим работы"]

        return response

    def _format_sources_fallback(self, search_results: List[Dict[str, Any]]) -> str:
        """Форматирует источники для fallback ответа"""
        if not search_results:
            return "Источники не найдены"

        sources = []
        for i, result in enumerate(search_results[:5], 1):
            metadata = result.get('metadata', {})
            title = metadata.get('document_title', 'Документ')
            sources.append(f"{i}. {title}")

        return "\n".join(sources)

    def _create_minimal_validation_report(self, response_id: str,
                                        error: str = None) -> ValidationReport:
        """Создает минимальный отчет валидации"""
        return ValidationReport(
            response_id=response_id,
            timestamp=datetime.now(),
            overall_score=0.7 if not error else 0.0,
            quality_grade=ResponseQuality.ACCEPTABLE if not error else ResponseQuality.POOR,
            total_issues=0 if not error else 1,
            critical_issues=0 if not error else 1,
            priority_fixes=[] if not error else [f"Ошибка валидации: {error}"]
        )

    # Публичные методы для управления системой

    def get_system_status(self) -> Dict[str, Any]:
        """Получает статус системы"""
        return {
            'status': 'operational',
            'components_initialized': len(self._get_used_components()),
            'usage_stats': self.usage_stats.copy(),
            'config': self.config.copy(),
            'version': '2.0',
            'last_update': datetime.now().isoformat()
        }

    def get_capabilities(self) -> List[str]:
        """Получает список возможностей системы"""
        capabilities = [
            "Интеллектуальная классификация запросов",
            "Гибридный поиск по правовым документам",
            "Семантическое сжатие истории разговоров",
            "Адаптивные промпты под уровень пользователя",
            "Правовая логика и инференс",
            "Структурированная генерация ответов",
            "Автоматическая валидация качества",
            "Поддержка иерархии правовых актов",
            "Выявление коллизий в законодательстве",
            "Анализ пробелов в правовом регулировании"
        ]

        if not self.config.get('enable_inference_engine', True):
            capabilities = [c for c in capabilities if 'инференс' not in c and 'логика' not in c]

        return capabilities

    async def update_configuration(self, new_config: Dict[str, Any]) -> bool:
        """Обновляет конфигурацию системы"""
        try:
            # Валидация конфигурации
            required_keys = ['enable_quality_validation', 'max_search_results', 'quality_threshold']
            for key in required_keys:
                if key not in new_config:
                    logger.warning(f"Отсутствует обязательный ключ конфигурации: {key}")

            # Обновление конфигурации
            self.config.update(new_config)
            logger.info("Конфигурация системы обновлена")
            return True

        except Exception as e:
            logger.error(f"Ошибка обновления конфигурации: {e}")
            return False

    def export_usage_analytics(self) -> Dict[str, Any]:
        """Экспортирует аналитику использования"""
        analytics = {
            'summary': {
                'total_consultations': self.usage_stats['total_consultations'],
                'success_rate': (self.usage_stats['successful_consultations'] /
                               max(self.usage_stats['total_consultations'], 1)) * 100,
                'average_quality': self.usage_stats['average_quality_score'],
                'error_rate': (self.usage_stats['error_count'] /
                             max(self.usage_stats['total_consultations'], 1)) * 100
            },
            'component_usage': self.usage_stats['component_usage'],
            'system_health': {
                'operational_status': 'healthy' if self.usage_stats['error_count'] < 10 else 'degraded',
                'quality_trend': 'stable',  # TODO: реализовать анализ трендов
                'performance_score': min(self.usage_stats['average_quality_score'] * 100, 100)
            },
            'export_timestamp': datetime.now().isoformat()
        }

        return analytics

# Глобальный экземпляр для использования в других модулях
enhanced_legal_assistant = EnhancedLegalAssistant()