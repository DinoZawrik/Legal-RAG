"""
Quality validation core (Context7 validated).

Main QualityValidator class with orchestration logic.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from collections import defaultdict

from .models import (
    ValidationCategory,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from . import helpers
from ..legal_ontology import LegalOntology
from ..enhanced_response_generator import StructuredResponse, ResponseSection, ResponseQuality

logger = logging.getLogger(__name__)


class QualityValidator:
    """
    Система валидации качества правовых консультаций.
    Выполняет комплексную проверку по всем критериям качества.
    """

    def __init__(self):
        self.legal_ontology = LegalOntology()

        # Справочники для валидации
        self.validation_rules = self._initialize_validation_rules()
        self.legal_terms_dictionary = self._initialize_legal_terms()
        self.common_mistakes = self._initialize_common_mistakes()
        self.safety_keywords = self._initialize_safety_keywords()

        # Пороги для оценки качества
        self.quality_thresholds = {
            'excellent': 0.95,
            'good': 0.85,
            'acceptable': 0.70,
            'poor': 0.50
        }

    def _initialize_validation_rules(self) -> Dict[ValidationCategory, Dict[str, Any]]:
        """Инициализация правил валидации"""
        return {
            ValidationCategory.FACTUAL_ACCURACY: {
                'required_elements': ['legal_references', 'document_citations', 'article_numbers'],
                'forbidden_elements': ['outdated_references', 'fictional_laws', 'unsupported_claims'],
                'reference_patterns': [
                    r'статья\s+\d+',
                    r'федеральный закон\s+?\s*\d+',
                    r'кодекс\s+\w+',
                    r'конституция\s+рф'
                ]
            },

            ValidationCategory.LEGAL_CORRECTNESS: {
                'hierarchy_rules': True,
                'temporal_validity': True,
                'jurisdiction_scope': True,
                'procedure_accuracy': True
            },

            ValidationCategory.LOGICAL_CONSISTENCY: {
                'premise_conclusion_alignment': True,
                'internal_contradictions': False,
                'inference_validity': True,
                'exception_handling': True
            },

            ValidationCategory.COMPLETENESS: {
                'required_sections': [ResponseSection.SUMMARY, ResponseSection.LEGAL_BASIS, ResponseSection.SOURCES],
                'min_content_length': 200,
                'min_sources': 1,
                'risk_warnings': True
            },

            ValidationCategory.USER_ADAPTATION: {
                'language_complexity': True,
                'terminology_explanation': True,
                'practical_guidance': True,
                'expertise_alignment': True
            },

            ValidationCategory.SAFETY: {
                'disclaimer_required': True,
                'risk_warnings': True,
                'no_guarantees': True,
                'consultation_recommendation': True
            }
        }

    def _initialize_legal_terms(self) -> Set[str]:
        """Инициализация словаря правовых терминов"""
        return {
            # Основные правовые понятия
            'право', 'обязанность', 'ответственность', 'правоотношение',
            'правосубъектность', 'правоспособность', 'дееспособность',

            # Виды ответственности
            'уголовная ответственность', 'административная ответственность',
            'гражданская ответственность', 'дисциплинарная ответственность',

            # Процедурные термины
            'подсудность', 'подведомственность', 'юрисдикция', 'компетенция',
            'исковая давность', 'процессуальные сроки', 'доказательства',

            # Документооборот
            'заявление', 'жалоба', 'ходатайство', 'определение', 'решение',
            'постановление', 'приговор', 'исполнительный лист',

            # Специальные процедуры
            'медиация', 'арбитраж', 'третейский суд', 'административное производство'
        }

    def _initialize_common_mistakes(self) -> Dict[str, List[str]]:
        """Инициализация типичных ошибок"""
        return {
            'terminology': [
                'административное наказание vs уголовное наказание',
                'договор vs соглашение vs контракт',
                'владение vs пользование vs распоряжение',
                'срок vs период vs время'
            ],

            'procedure': [
                'неправильные сроки подачи жалоб',
                'путаница в подсудности',
                'неверные требования к документам',
                'неточности в порядке обжалования'
            ],

            'hierarchy': [
                'ссылка на отмененные нормы',
                'применение норм низшей силы при наличии высших',
                'игнорирование специальных норм',
                'неучет региональной специфики'
            ],

            'logic': [
                'противоречие между выводами',
                'необоснованные обобщения',
                'логические скачки в рассуждениях',
                'игнорирование исключений'
            ]
        }

    def _initialize_safety_keywords(self) -> Dict[str, List[str]]:
        """Инициализация ключевых слов для проверки безопасности"""
        return {
            'dangerous_advice': [
                'гарантированно получите',
                'обязательно выиграете',
                'никаких рисков',
                'точно избежите ответственности'
            ],

            'missing_disclaimers': [
                'окончательное решение',
                'единственно правильный способ',
                'всегда действует',
                'никогда не применяется'
            ],

            'oversimplification': [
                'просто сделайте',
                'достаточно только',
                'никаких проблем не будет',
                'формальность'
            ]
        }

    async def validate_response(self, response: StructuredResponse,
                              search_results: List[Dict[str, Any]] = None,
                              original_query: str = None) -> ValidationReport:
        """
        Выполняет комплексную валидацию ответа.

        Args:
            response: Структурированный ответ для валидации
            search_results: Исходные результаты поиска
            original_query: Оригинальный запрос пользователя

        Returns:
            Отчет о валидации с выявленными проблемами
        """
        try:
            logger.info(f"Начало валидации ответа {response.response_id}")

            report = ValidationReport(
                response_id=response.response_id,
                timestamp=datetime.now(),
                overall_score=0.0, # Будет пересчитано
                quality_grade=ResponseQuality.POOR # Будет пересчитано
            )

            # 1. Фактическая проверка
            factual_issues = await self._validate_factual_accuracy(response, search_results)

            # 2. Правовая корректность
            legal_issues = await self._validate_legal_correctness(response)

            # 3. Логическая последовательность
            logic_issues = await self._validate_logical_consistency(response)

            # 4. Полнота
            completeness_issues = await self._validate_completeness(response)

            # 5. Релевантность
            relevance_issues = await self._validate_relevance(response, original_query)

            # 6. Адаптация к пользователю
            adaptation_issues = await self._validate_user_adaptation(response)

            # 7. Формальные требования
            formal_issues = await self._validate_formal_requirements(response)

            # 8. Безопасность советов
            safety_issues = await self._validate_safety(response)

            # Сбор всех проблем
            all_issues = (factual_issues + legal_issues + logic_issues +
                         completeness_issues + relevance_issues + adaptation_issues +
                         formal_issues + safety_issues)

            # Группировка проблем
            report.issues_by_category = helpers.group_issues_by_category(all_issues)
            report.issues_by_severity = helpers.group_issues_by_severity(all_issues)

            # Статистика
            report.total_issues = len(all_issues)
            report.critical_issues = len([i for i in all_issues if i.severity == ValidationSeverity.CRITICAL])
            report.auto_fixable_issues = len([i for i in all_issues if i.auto_fix_available])

            # Расчет общей оценки
            report.overall_score = helpers.calculate_overall_score(self, all_issues, response)
            report.quality_grade = helpers.determine_quality_grade(self, report.overall_score)

            # Генерация рекомендаций
            report.priority_fixes = helpers.generate_priority_fixes(all_issues)
            report.improvement_suggestions = helpers.generate_improvement_suggestions(all_issues, response)

            logger.info(f"Валидация завершена. Найдено {report.total_issues} проблем, оценка: {report.overall_score:.2f}")
            return report

        except Exception as e:
            logger.error(f"Ошибка при валидации ответа: {e}")
            return helpers.create_error_report(response.response_id, str(e))

    async def _validate_factual_accuracy(self, response: StructuredResponse,
                                       search_results: List[Dict[str, Any]] = None) -> List[ValidationIssue]:
        """Валидация фактической точности"""
        issues = []

        try:
            # Проверка правовых ссылок
            legal_refs = helpers.extract_legal_references(self, response)

            for ref in legal_refs:
                # Проверка существования статьи
                if not helpers.verify_legal_reference(self, ref, search_results):
                    issues.append(ValidationIssue(
                        issue_id=f"fact_ref_{len(issues)}",
                        category=ValidationCategory.FACTUAL_ACCURACY,
                        severity=ValidationSeverity.CRITICAL,
                        title="Неверная правовая ссылка",
                        description=f"Не удалось подтвердить существование: {ref}",
                        recommendations=["Проверить точность ссылки", "Найти альтернативные источники"],
                        affected_elements=[ref]
                    ))

            # Проверка дат и временных периодов
            dates_issues = helpers.validate_dates_and_periods(self, response)
            issues.extend(dates_issues)

            # Проверка числовых данных
            numeric_issues = helpers.validate_numeric_data(self, response)
            issues.extend(numeric_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке фактической точности: {e}")

        return issues

    async def _validate_legal_correctness(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация правовой корректности"""
        issues = []

        try:
            # Проверка иерархии правовых актов
            hierarchy_issues = helpers.check_legal_hierarchy(self, response)
            issues.extend(hierarchy_issues)

            # Проверка актуальности законодательства
            actuality_issues = helpers.check_legal_actuality(self, response)
            issues.extend(actuality_issues)

            # Проверка юрисдикции
            jurisdiction_issues = helpers.check_jurisdiction_scope(self, response)
            issues.extend(jurisdiction_issues)

            # Проверка процедурной корректности
            procedure_issues = helpers.check_procedure_correctness(self, response)
            issues.extend(procedure_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке правовой корректности: {e}")

        return issues

    async def _validate_logical_consistency(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация логической последовательности"""
        issues = []

        try:
            # Проверка связи между посылками и выводами
            if response.inferences:
                for inference in response.inferences:
                    if not helpers.validate_inference_logic(self, inference):
                        issues.append(ValidationIssue(
                            issue_id=f"logic_inference_{len(issues)}",
                            category=ValidationCategory.LOGICAL_CONSISTENCY,
                            severity=ValidationSeverity.HIGH,
                            title="Нарушение логики вывода",
                            description=f"Вывод '{inference.conclusion}' не следует из посылок",
                            recommendations=["Пересмотреть логическую цепочку", "Добавить промежуточные шаги"],
                            affected_elements=[inference.conclusion]
                        ))

            # Проверка внутренних противоречий
            contradictions = helpers.find_internal_contradictions(self, response)
            for contradiction in contradictions:
                issues.append(ValidationIssue(
                    issue_id=f"logic_contradiction_{len(issues)}",
                    category=ValidationCategory.LOGICAL_CONSISTENCY,
                    severity=ValidationSeverity.HIGH,
                    title="Внутреннее противоречие",
                    description=f"Противоречие между: {contradiction['statement1']} и {contradiction['statement2']}",
                    recommendations=["Устранить противоречие", "Добавить пояснения о контексте"],
                    affected_elements=[contradiction['statement1'], contradiction['statement2']]
                ))

        except Exception as e:
            logger.error(f"Ошибка при проверке логической последовательности: {e}")

        return issues

    async def _validate_completeness(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация полноты ответа"""
        issues = []

        try:
            required_sections = self.validation_rules[ValidationCategory.COMPLETENESS]['required_sections']

            # Проверка обязательных секций
            for required_section in required_sections:
                if required_section not in response.sections:
                    issues.append(ValidationIssue(
                        issue_id=f"completeness_section_{required_section.value}",
                        category=ValidationCategory.COMPLETENESS,
                        severity=ValidationSeverity.HIGH,
                        title=f"Отсутствует обязательная секция",
                        description=f"Не найдена секция: {required_section.value}",
                        recommendations=[f"Добавить секцию {required_section.value}"],
                        auto_fix_available=True,
                        affected_elements=[required_section.value]
                    ))

            # Проверка минимальной длины контента
            min_length = self.validation_rules[ValidationCategory.COMPLETENESS]['min_content_length']
            total_content = " ".join(response.sections.values())

            if len(total_content) < min_length:
                issues.append(ValidationIssue(
                    issue_id="completeness_length",
                    category=ValidationCategory.COMPLETENESS,
                    severity=ValidationSeverity.MEDIUM,
                    title="Недостаточная детализация",
                    description=f"Общая длина ответа ({len(total_content)} символов) меньше минимума ({min_length})",
                    recommendations=["Добавить более детальные объяснения", "Расширить правовой анализ"],
                    affected_elements=["общая длина контента"]
                ))

            # Проверка наличия источников
            min_sources = self.validation_rules[ValidationCategory.COMPLETENESS]['min_sources']
            if len(response.sources) < min_sources:
                issues.append(ValidationIssue(
                    issue_id="completeness_sources",
                    category=ValidationCategory.COMPLETENESS,
                    severity=ValidationSeverity.HIGH,
                    title="Недостаточно источников",
                    description=f"Найдено {len(response.sources)} источников, минимум: {min_sources}",
                    recommendations=["Добавить ссылки на нормативные акты", "Указать дополнительные источники"],
                    affected_elements=["список источников"]
                ))

        except Exception as e:
            logger.error(f"Ошибка при проверке полноты: {e}")

        return issues

    async def _validate_relevance(self, response: StructuredResponse,
                                original_query: str = None) -> List[ValidationIssue]:
        """Валидация релевантности"""
        issues = []

        try:
            if not original_query:
                return issues

            # Извлечение ключевых слов из запроса
            query_keywords = set(original_query.lower().split())

            # Проверка присутствия ключевых слов в ответе
            response_text = " ".join(response.sections.values()).lower()
            response_keywords = set(response_text.split())

            overlap = len(query_keywords & response_keywords)
            relevance_score = overlap / len(query_keywords) if query_keywords else 0

            if relevance_score < 0.3: # Менее 30% пересечения
                issues.append(ValidationIssue(
                    issue_id="relevance_keywords",
                    category=ValidationCategory.RELEVANCE,
                    severity=ValidationSeverity.MEDIUM,
                    title="Низкая релевантность запросу",
                    description=f"Пересечение ключевых слов: {relevance_score:.1%}",
                    recommendations=["Лучше адресовать конкретный вопрос", "Добавить прямые ответы на запрос"],
                    affected_elements=["общая релевантность"]
                ))

        except Exception as e:
            logger.error(f"Ошибка при проверке релевантности: {e}")

        return issues

    async def _validate_user_adaptation(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация адаптации к пользователю"""
        issues = []

        try:
            # Проверка соответствия языка уровню экспертизы
            language_issues = helpers.check_language_complexity(self, response)
            issues.extend(language_issues)

            # Проверка объяснения терминологии
            terminology_issues = helpers.check_terminology_explanation(self, response)
            issues.extend(terminology_issues)

            # Проверка практических рекомендаций
            practical_issues = helpers.check_practical_guidance(self, response)
            issues.extend(practical_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке адаптации к пользователю: {e}")

        return issues

    async def _validate_formal_requirements(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация формальных требований"""
        issues = []

        try:
            # Проверка структуры ответа
            structure_issues = helpers.check_response_structure(self, response)
            issues.extend(structure_issues)

            # Проверка форматирования
            formatting_issues = helpers.check_formatting(self, response)
            issues.extend(formatting_issues)

            # Проверка ссылок и цитат
            citation_issues = helpers.check_citations_format(self, response)
            issues.extend(citation_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке формальных требований: {e}")

        return issues

    async def _validate_safety(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация безопасности советов"""
        issues = []

        try:
            # Проверка наличия дисклеймеров
            disclaimer_issues = helpers.check_disclaimers(self, response)
            issues.extend(disclaimer_issues)

            # Проверка предупреждений о рисках
            risk_warning_issues = helpers.check_risk_warnings(self, response)
            issues.extend(risk_warning_issues)

            # Проверка на опасные советы
            dangerous_advice_issues = helpers.check_dangerous_advice(self, response)
            issues.extend(dangerous_advice_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке безопасности: {e}")

        return issues

    def format_validation_report(self, report: ValidationReport,
                               detailed: bool = True) -> str:
        """Форматирует отчет валидации для вывода"""
        return helpers.format_validation_report(report, detailed)


__all__ = ["QualityValidator"]
