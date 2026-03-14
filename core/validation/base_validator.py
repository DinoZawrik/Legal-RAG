"""
Базовый валидатор с общей функциональностью и инициализацией.
Предоставляет общие методы и конфигурацию для всех валидаторов.
"""

import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import re

from .types import (
    ValidationSeverity, ValidationCategory, ValidationIssue, ValidationReport,
    ValidationRules, LegalTermsSet, CommonMistakes, SafetyKeywords
)
from ..legal_ontology import LegalOntology, DocumentType
from ..smart_query_classifier import QueryType, UserExpertiseLevel
from ..enhanced_response_generator import StructuredResponse, ResponseSection, ResponseQuality

logger = logging.getLogger(__name__)

class BaseValidator:
    """
    Базовый класс для всех валидаторов.
    Содержит общую функциональность и правила валидации.
    """

    def __init__(self):
        self.legal_ontology = LegalOntology()

        # Инициализация общих справочников
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

    def _initialize_validation_rules(self) -> ValidationRules:
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

    def _initialize_legal_terms(self) -> LegalTermsSet:
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

    def _initialize_common_mistakes(self) -> CommonMistakes:
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

    def _initialize_safety_keywords(self) -> SafetyKeywords:
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

    def extract_legal_references(self, response: StructuredResponse) -> List[str]:
        """Извлекает правовые ссылки из ответа"""
        references = []
        response_text = " ".join(response.sections.values())

        patterns = self.validation_rules[ValidationCategory.FACTUAL_ACCURACY]['reference_patterns']

        for pattern in patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            references.extend(matches)

        return list(set(references)) # Убираем дубликаты

    def verify_legal_reference(self, reference: str,
                              search_results: List[Dict[str, Any]] = None) -> bool:
        """Проверяет существование правовой ссылки"""
        if not search_results:
            return True # Не можем проверить без исходных данных

        # Поиск ссылки в исходных документах
        ref_lower = reference.lower()

        for result in search_results:
            content = result.get('content', '').lower()
            metadata = result.get('metadata', {})

            if ref_lower in content or ref_lower in str(metadata).lower():
                return True

        return False

    def create_issue(self, issue_id: str, category: ValidationCategory,
                    severity: ValidationSeverity, title: str, description: str,
                    recommendations: List[str] = None, auto_fix_available: bool = False,
                    affected_elements: List[str] = None, section: ResponseSection = None,
                    confidence: float = 1.0) -> ValidationIssue:
        """Создает объект ValidationIssue с переданными параметрами"""
        return ValidationIssue(
            issue_id=issue_id,
            category=category,
            severity=severity,
            title=title,
            description=description,
            section=section,
            recommendations=recommendations or [],
            auto_fix_available=auto_fix_available,
            affected_elements=affected_elements or [],
            confidence=confidence
        )

    def validate_dates_and_periods(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет корректность дат и временных периодов"""
        issues = []

        # Паттерны для поиска дат
        date_patterns = [
            r'\d{1,2}\.\d{1,2}\.\d{4}',
            r'\d{4}\s*год[ау]?',
            r'с\s+\d{4}\s*года',
            r'до\s+\d{4}\s*года'
        ]

        response_text = " ".join(response.sections.values())

        for pattern in date_patterns:
            matches = re.findall(pattern, response_text)
            for match in matches:
                # Базовая проверка реалистичности дат
                if '2025' in match or '2026' in match: # Будущие годы
                    issues.append(self.create_issue(
                        issue_id=f"date_future_{len(issues)}",
                        category=ValidationCategory.FACTUAL_ACCURACY,
                        severity=ValidationSeverity.MEDIUM,
                        title="Подозрительная дата",
                        description=f"Найдена дата в будущем: {match}",
                        recommendations=["Проверить корректность даты"],
                        affected_elements=[match]
                    ))

        return issues

    def validate_numeric_data(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет корректность числовых данных"""
        issues = []

        # Поиск подозрительных числовых значений
        response_text = " ".join(response.sections.values())

        # Паттерны для штрафов и санкций
        penalty_patterns = [
            r'штраф\s+(\d+(?:\s?\d+)*)\s*рублей?',
            r'санкция\s+(\d+(?:\s?\d+)*)\s*рублей?',
            r'взыскание\s+(\d+(?:\s?\d+)*)\s*рублей?'
        ]

        for pattern in penalty_patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            for match in matches:
                try:
                    amount = int(match.replace(' ', ''))

                    # Проверка реалистичности сумм
                    if amount > 10000000: # Более 10 млн рублей
                        issues.append(self.create_issue(
                            issue_id=f"numeric_suspicious_{len(issues)}",
                            category=ValidationCategory.FACTUAL_ACCURACY,
                            severity=ValidationSeverity.MEDIUM,
                            title="Подозрительная сумма",
                            description=f"Очень большая сумма: {amount:,} рублей",
                            recommendations=["Проверить корректность суммы", "Уточнить источник данных"],
                            affected_elements=[f"{amount:,} рублей"]
                        ))
                except ValueError:
                    pass # Игнорируем некорректные числа

        return issues

    async def validate_factual_accuracy(self, response: StructuredResponse,
                                       search_results: List[Dict[str, Any]] = None) -> List[ValidationIssue]:
        """Валидация фактической точности"""
        issues = []

        try:
            # Проверка правовых ссылок
            legal_refs = self.extract_legal_references(response)

            for ref in legal_refs:
                # Проверка существования статьи
                if not self.verify_legal_reference(ref, search_results):
                    issues.append(self.create_issue(
                        issue_id=f"fact_ref_{len(issues)}",
                        category=ValidationCategory.FACTUAL_ACCURACY,
                        severity=ValidationSeverity.CRITICAL,
                        title="Неверная правовая ссылка",
                        description=f"Не удалось подтвердить существование: {ref}",
                        recommendations=["Проверить точность ссылки", "Найти альтернативные источники"],
                        affected_elements=[ref]
                    ))

            # Проверка дат и временных периодов
            dates_issues = self.validate_dates_and_periods(response)
            issues.extend(dates_issues)

            # Проверка числовых данных
            numeric_issues = self.validate_numeric_data(response)
            issues.extend(numeric_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке фактической точности: {e}")

        return issues