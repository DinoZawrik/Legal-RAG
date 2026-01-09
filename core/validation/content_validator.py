"""
Валидатор содержания и структуры ответов.
Проверяет логическую последовательность, полноту, релевантность и адаптацию к пользователю.
"""

import logging
from typing import Dict, List, Optional, Any, Set
from collections import defaultdict

from .types import ValidationSeverity, ValidationCategory, ValidationIssue
from .base_validator import BaseValidator
from ..enhanced_response_generator import StructuredResponse, ResponseSection
from ..smart_query_classifier import UserExpertiseLevel

logger = logging.getLogger(__name__)

class ContentValidator(BaseValidator):
    """
    Валидатор для проверки содержания и структуры ответов.
    Проверяет логику, полноту, релевантность и адаптацию к пользователю.
    """

    async def validate_logical_consistency(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация логической последовательности"""
        issues = []

        try:
            # Проверка связи между посылками и выводами
            if response.inferences:
                for inference in response.inferences:
                    if not self._validate_inference_logic(inference):
                        issues.append(self.create_issue(
                            issue_id=f"logic_inference_{len(issues)}",
                            category=ValidationCategory.LOGICAL_CONSISTENCY,
                            severity=ValidationSeverity.HIGH,
                            title="Нарушение логики вывода",
                            description=f"Вывод '{inference.conclusion}' не следует из посылок",
                            recommendations=["Пересмотреть логическую цепочку", "Добавить промежуточные шаги"],
                            affected_elements=[inference.conclusion]
                        ))

            # Проверка внутренних противоречий
            contradictions = self._find_internal_contradictions(response)
            for contradiction in contradictions:
                issues.append(self.create_issue(
                    issue_id=f"logic_contradiction_{len(issues)}",
                    category=ValidationCategory.LOGICAL_CONSISTENCY,
                    severity=ValidationSeverity.HIGH,
                    title="Внутреннее противоречие",
                    description=f"Противоречие между: {contradiction['statement1']} и {contradiction['statement2']}",
                    recommendations=["Устранить противоречие", "Добавить пояснения о контексте", "Указать условия применимости"],
                    affected_elements=[contradiction['statement1'], contradiction['statement2']]
                ))

            # Проверка логических переходов между секциями
            section_coherence_issues = self._check_section_coherence(response)
            issues.extend(section_coherence_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке логической последовательности: {e}")

        return issues

    async def validate_completeness(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация полноты ответа"""
        issues = []

        try:
            required_sections = self.validation_rules[ValidationCategory.COMPLETENESS]['required_sections']

            # Проверка обязательных секций
            for required_section in required_sections:
                if required_section not in response.sections:
                    issues.append(self.create_issue(
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
                issues.append(self.create_issue(
                    issue_id="completeness_length",
                    category=ValidationCategory.COMPLETENESS,
                    severity=ValidationSeverity.MEDIUM,
                    title="Недостаточная детализация",
                    description=f"Общая длина ответа ({len(total_content)} символов) меньше минимума ({min_length})",
                    recommendations=["Добавить более детальные объяснения", "Расширить правовой анализ", "Включить больше примеров"],
                    affected_elements=["общая длина контента"]
                ))

            # Проверка наличия источников
            min_sources = self.validation_rules[ValidationCategory.COMPLETENESS]['min_sources']
            if len(response.sources) < min_sources:
                issues.append(self.create_issue(
                    issue_id="completeness_sources",
                    category=ValidationCategory.COMPLETENESS,
                    severity=ValidationSeverity.HIGH,
                    title="Недостаточно источников",
                    description=f"Найдено {len(response.sources)} источников, минимум: {min_sources}",
                    recommendations=["Добавить ссылки на нормативные акты", "Указать дополнительные источники", "Включить судебную практику"],
                    affected_elements=["список источников"]
                ))

            # Проверка глубины анализа по разделам
            depth_issues = self._check_analysis_depth(response)
            issues.extend(depth_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке полноты: {e}")

        return issues

    async def validate_relevance(self, response: StructuredResponse,
                               original_query: str = None) -> List[ValidationIssue]:
        """Валидация релевантности"""
        issues = []

        try:
            if not original_query:
                return issues

            # Извлечение ключевых слов из запроса
            query_keywords = set(original_query.lower().split())

            # Удаление стоп-слов
            stop_words = {'что', 'как', 'где', 'когда', 'почему', 'какой', 'какая', 'какие',
                         'в', 'на', 'за', 'под', 'над', 'при', 'с', 'для', 'от', 'до', 'по'}
            query_keywords = query_keywords - stop_words

            # Проверка присутствия ключевых слов в ответе
            response_text = " ".join(response.sections.values()).lower()
            response_keywords = set(response_text.split())

            overlap = len(query_keywords & response_keywords)
            relevance_score = overlap / len(query_keywords) if query_keywords else 0

            if relevance_score < 0.3:  # Менее 30% пересечения
                issues.append(self.create_issue(
                    issue_id="relevance_keywords",
                    category=ValidationCategory.RELEVANCE,
                    severity=ValidationSeverity.MEDIUM,
                    title="Низкая релевантность запросу",
                    description=f"Пересечение ключевых слов: {relevance_score:.1%}",
                    recommendations=["Лучше адресовать конкретный вопрос", "Добавить прямые ответы на запрос", "Включить больше релевантной терминологии"],
                    affected_elements=["общая релевантность"]
                ))

            # Проверка соответствия типа запроса и ответа
            query_type_issues = self._check_query_type_alignment(response, original_query)
            issues.extend(query_type_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке релевантности: {e}")

        return issues

    async def validate_user_adaptation(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация адаптации к пользователю"""
        issues = []

        try:
            # Проверка соответствия языка уровню экспертизы
            language_issues = self._check_language_complexity(response)
            issues.extend(language_issues)

            # Проверка объяснения терминологии
            terminology_issues = self._check_terminology_explanation(response)
            issues.extend(terminology_issues)

            # Проверка практических рекомендаций
            practical_issues = self._check_practical_guidance(response)
            issues.extend(practical_issues)

            # Проверка структуры подачи информации
            structure_issues = self._check_information_structure(response)
            issues.extend(structure_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке адаптации к пользователю: {e}")

        return issues

    def _validate_inference_logic(self, inference) -> bool:
        """Проверяет логическую корректность вывода"""
        # Упрощенная проверка логики
        if not hasattr(inference, 'logical_chain') or not inference.logical_chain:
            return False

        # Проверка минимальной длины логической цепи
        if len(inference.logical_chain) < 2:
            return False

        # Проверка связности шагов (базовая)
        return True

    def _find_internal_contradictions(self, response: StructuredResponse) -> List[Dict[str, str]]:
        """Поиск внутренних противоречий в ответе"""
        contradictions = []

        # Извлечение утверждений из разных секций
        statements = []
        for section, content in response.sections.items():
            sentences = content.split('.')
            for sentence in sentences:
                if len(sentence.strip()) > 20:  # Фильтруем короткие фразы
                    statements.append({
                        'text': sentence.strip(),
                        'section': section
                    })

        # Поиск противоречивых утверждений
        contradiction_pairs = [
            (['обязан', 'должен'], ['не обязан', 'не должен']),
            (['разрешено', 'можно'], ['запрещено', 'нельзя']),
            (['всегда'], ['никогда']),
            (['требуется'], ['не требуется']),
            (['имеет право'], ['не имеет права']),
            (['возможно'], ['невозможно'])
        ]

        for i, stmt1 in enumerate(statements):
            for j, stmt2 in enumerate(statements[i+1:], i+1):
                for positive_words, negative_words in contradiction_pairs:
                    has_positive1 = any(word in stmt1['text'].lower() for word in positive_words)
                    has_negative2 = any(word in stmt2['text'].lower() for word in negative_words)

                    if has_positive1 and has_negative2:
                        # Дополнительная проверка на общий объект
                        words1 = set(stmt1['text'].lower().split())
                        words2 = set(stmt2['text'].lower().split())
                        if len(words1 & words2) >= 2:  # Минимум 2 общих слова
                            contradictions.append({
                                'statement1': stmt1['text'][:100] + "..." if len(stmt1['text']) > 100 else stmt1['text'],
                                'statement2': stmt2['text'][:100] + "..." if len(stmt2['text']) > 100 else stmt2['text'],
                                'section1': stmt1['section'].value,
                                'section2': stmt2['section'].value
                            })

        return contradictions

    def _check_section_coherence(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет логическую связность между секциями"""
        issues = []

        sections_list = list(response.sections.items())

        for i, (section1, content1) in enumerate(sections_list):
            for section2, content2 in sections_list[i+1:]:
                # Проверка тематического соответствия между секциями
                if section1 == ResponseSection.SUMMARY and section2 == ResponseSection.LEGAL_BASIS:
                    # Краткий ответ должен соответствовать правовому обоснованию
                    coherence_score = self._calculate_content_similarity(content1, content2)

                    if coherence_score < 0.2:  # Низкая связность
                        issues.append(self.create_issue(
                            issue_id=f"coherence_{section1.value}_{section2.value}",
                            category=ValidationCategory.LOGICAL_CONSISTENCY,
                            severity=ValidationSeverity.MEDIUM,
                            title="Низкая связность между секциями",
                            description=f"Секции {section1.value} и {section2.value} плохо связаны тематически",
                            recommendations=["Улучшить связность изложения", "Добавить переходные фразы", "Проверить соответствие выводов обоснованию"],
                            affected_elements=[section1.value, section2.value]
                        ))

        return issues

    def _check_analysis_depth(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет глубину анализа в разных секциях"""
        issues = []

        # Проверка правового обоснования
        legal_basis = response.sections.get(ResponseSection.LEGAL_BASIS, '')
        if legal_basis:
            # Минимальные требования к правовому анализу
            required_elements = ['статья', 'закон', 'норма', 'право']
            found_elements = [elem for elem in required_elements if elem in legal_basis.lower()]

            if len(found_elements) < 2:
                issues.append(self.create_issue(
                    issue_id="depth_legal_basis",
                    category=ValidationCategory.COMPLETENESS,
                    severity=ValidationSeverity.MEDIUM,
                    title="Поверхностное правовое обоснование",
                    description="Недостаточно правовых терминов и ссылок в обосновании",
                    recommendations=["Добавить больше правовых ссылок", "Углубить правовой анализ", "Включить конкретные нормы"],
                    section=ResponseSection.LEGAL_BASIS,
                    affected_elements=["глубина правового анализа"]
                ))

        return issues

    def _check_query_type_alignment(self, response: StructuredResponse, query: str) -> List[ValidationIssue]:
        """Проверяет соответствие типа ответа типу запроса"""
        issues = []

        query_lower = query.lower()

        # Определение типа запроса и проверка соответствия ответа
        if any(word in query_lower for word in ['как', 'каким образом', 'процедура']):
            # Процедурный вопрос - должна быть секция с практическими шагами
            if ResponseSection.PRACTICAL_STEPS not in response.sections:
                issues.append(self.create_issue(
                    issue_id="relevance_procedure_missing",
                    category=ValidationCategory.RELEVANCE,
                    severity=ValidationSeverity.HIGH,
                    title="Отсутствует процедурная информация",
                    description="Вопрос о процедуре, но нет практических шагов",
                    recommendations=["Добавить секцию с практическими шагами", "Описать пошаговую процедуру"],
                    affected_elements=["процедурная информация"]
                ))

        elif any(word in query_lower for word in ['что такое', 'определение', 'понятие']):
            # Вопрос на определение - должно быть четкое объяснение
            summary = response.sections.get(ResponseSection.SUMMARY, '')
            if not summary or len(summary) < 50:
                issues.append(self.create_issue(
                    issue_id="relevance_definition_weak",
                    category=ValidationCategory.RELEVANCE,
                    severity=ValidationSeverity.MEDIUM,
                    title="Слабое определение понятия",
                    description="Вопрос на определение, но краткий ответ недостаточно информативен",
                    recommendations=["Дать четкое определение", "Расширить краткий ответ", "Добавить ключевые характеристики"],
                    section=ResponseSection.SUMMARY,
                    affected_elements=["определение понятия"]
                ))

        return issues

    def _check_language_complexity(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет соответствие языка уровню пользователя"""
        issues = []

        response_text = " ".join(response.sections.values())

        # Подсчет сложных терминов
        complex_terms = 0
        for term in self.legal_terms_dictionary:
            if term in response_text.lower():
                complex_terms += 1

        # Оценка сложности для разных уровней
        if hasattr(response, 'user_expertise'):
            if response.user_expertise == UserExpertiseLevel.BEGINNER:
                if complex_terms > 5:  # Более 5 сложных терминов
                    issues.append(self.create_issue(
                        issue_id="language_too_complex",
                        category=ValidationCategory.USER_ADAPTATION,
                        severity=ValidationSeverity.MEDIUM,
                        title="Язык слишком сложен для начинающего",
                        description=f"Найдено {complex_terms} сложных правовых терминов",
                        recommendations=["Упростить язык", "Добавить объяснения терминов", "Использовать более простые аналогии"],
                        affected_elements=["общая сложность языка"]
                    ))

            elif response.user_expertise == UserExpertiseLevel.EXPERT:
                if complex_terms < 2:  # Менее 2 профессиональных терминов
                    issues.append(self.create_issue(
                        issue_id="language_too_simple",
                        category=ValidationCategory.USER_ADAPTATION,
                        severity=ValidationSeverity.LOW,
                        title="Язык слишком прост для эксперта",
                        description="Недостаточно профессиональной терминологии",
                        recommendations=["Добавить профессиональные термины", "Углубить анализ", "Использовать специализированную лексику"],
                        affected_elements=["уровень профессионализма языка"]
                    ))

        return issues

    def _check_terminology_explanation(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет объяснение терминологии"""
        issues = []

        if hasattr(response, 'user_expertise') and response.user_expertise == UserExpertiseLevel.BEGINNER:
            response_text = " ".join(response.sections.values()).lower()

            # Поиск необъясненных терминов
            unexplained_terms = []
            for term in list(self.legal_terms_dictionary)[:10]:  # Проверяем первые 10 терминов
                if term in response_text:
                    # Проверяем, есть ли объяснение рядом
                    term_index = response_text.find(term)
                    surrounding_text = response_text[max(0, term_index-50):term_index+100]

                    explanation_indicators = ['это означает', 'то есть', '(', 'называется', 'представляет собой']
                    has_explanation = any(indicator in surrounding_text for indicator in explanation_indicators)

                    if not has_explanation:
                        unexplained_terms.append(term)

            if unexplained_terms:
                issues.append(self.create_issue(
                    issue_id="terminology_unexplained",
                    category=ValidationCategory.USER_ADAPTATION,
                    severity=ValidationSeverity.MEDIUM,
                    title="Необъясненные термины",
                    description=f"Термины без объяснений: {', '.join(unexplained_terms[:3])}",
                    recommendations=["Добавить объяснения терминов", "Использовать простые синонимы", "Включить определения в скобках"],
                    affected_elements=unexplained_terms[:3]
                ))

        return issues

    def _check_practical_guidance(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет наличие практических рекомендаций"""
        issues = []

        practical_section = response.sections.get(ResponseSection.PRACTICAL_STEPS)

        if hasattr(response, 'user_expertise'):
            if not practical_section and response.user_expertise in [UserExpertiseLevel.BEGINNER, UserExpertiseLevel.INTERMEDIATE]:
                issues.append(self.create_issue(
                    issue_id="practical_missing",
                    category=ValidationCategory.USER_ADAPTATION,
                    severity=ValidationSeverity.MEDIUM,
                    title="Отсутствуют практические рекомендации",
                    description="Для данного уровня пользователя нужны практические советы",
                    recommendations=["Добавить секцию с практическими шагами", "Указать конкретные действия", "Включить пошаговое руководство"],
                    auto_fix_available=True,
                    affected_elements=["практические рекомендации"]
                ))

        return issues

    def _check_information_structure(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет структуру подачи информации для пользователя"""
        issues = []

        if hasattr(response, 'user_expertise'):
            if response.user_expertise == UserExpertiseLevel.BEGINNER:
                # Для новичков важна четкая структура "от простого к сложному"
                if ResponseSection.SUMMARY not in response.sections:
                    issues.append(self.create_issue(
                        issue_id="structure_no_summary",
                        category=ValidationCategory.USER_ADAPTATION,
                        severity=ValidationSeverity.HIGH,
                        title="Отсутствует краткий ответ для новичка",
                        description="Новичкам нужен простой краткий ответ в начале",
                        recommendations=["Добавить краткое резюме", "Начать с простого объяснения"],
                        auto_fix_available=True,
                        affected_elements=["структура для новичка"]
                    ))

        return issues

    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Вычисляет семантическое сходство между двумя текстами"""
        # Упрощенная оценка сходства на основе пересечения слов
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        # Исключаем служебные слова
        stop_words = {'и', 'в', 'на', 'с', 'по', 'для', 'от', 'до', 'при', 'за'}
        words1 = words1 - stop_words
        words2 = words2 - stop_words

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0