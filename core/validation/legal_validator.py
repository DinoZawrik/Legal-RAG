"""
Валидатор правовой корректности.
Проверяет правовую корректность, иерархию актов, актуальность законодательства,
юрисдикцию и процедурную корректность.
"""

import logging
from typing import Dict, List, Optional, Any

from .types import ValidationSeverity, ValidationCategory, ValidationIssue
from .base_validator import BaseValidator
from ..enhanced_response_generator import StructuredResponse, ResponseSection

logger = logging.getLogger(__name__)

class LegalValidator(BaseValidator):
    """
    Валидатор для проверки правовой корректности ответов.
    Проверяет иерархию правовых актов, актуальность, юрисдикцию и процедуры.
    """

    async def validate_legal_correctness(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация правовой корректности"""
        issues = []

        try:
            # Проверка иерархии правовых актов
            hierarchy_issues = self._check_legal_hierarchy(response)
            issues.extend(hierarchy_issues)

            # Проверка актуальности законодательства
            actuality_issues = self._check_legal_actuality(response)
            issues.extend(actuality_issues)

            # Проверка юрисдикции
            jurisdiction_issues = self._check_jurisdiction_scope(response)
            issues.extend(jurisdiction_issues)

            # Проверка процедурной корректности
            procedure_issues = self._check_procedure_correctness(response)
            issues.extend(procedure_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке правовой корректности: {e}")

        return issues

    def _check_legal_hierarchy(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет соблюдение иерархии правовых актов"""
        issues = []

        # Проверка приоритета источников
        if response.sources:
            for i, source in enumerate(response.sources):
                source_type = source.get('type', '').lower()

                # Поиск некорректного приоритета
                for j, other_source in enumerate(response.sources[i+1:], i+1):
                    other_type = other_source.get('type', '').lower()

                    # Конституция должна быть выше федерального закона
                    if 'федеральный закон' in source_type and 'конституция' in other_type:
                        issues.append(self.create_issue(
                            issue_id=f"hierarchy_order_{i}_{j}",
                            category=ValidationCategory.LEGAL_CORRECTNESS,
                            severity=ValidationSeverity.MEDIUM,
                            title="Нарушение иерархии актов",
                            description="Конституция должна упоминаться раньше федеральных законов",
                            recommendations=["Изменить порядок источников", "Указать иерархию юридической силы"],
                            affected_elements=[source.get('title', ''), other_source.get('title', '')]
                        ))

        # Дополнительная проверка иерархии в тексте
        response_text = " ".join(response.sections.values()).lower()

        # Проверка корректного применения иерархии норм
        hierarchy_violations = [
            ('подзаконный акт', 'федеральный закон', 'Подзаконный акт не может отменять федеральный закон'),
            ('региональный закон', 'федеральный закон', 'Региональный закон не может противоречить федеральному'),
            ('ведомственная инструкция', 'кодекс', 'Ведомственная инструкция не может изменять кодекс')
        ]

        for lower_act, higher_act, violation_msg in hierarchy_violations:
            if lower_act in response_text and higher_act in response_text:
                # Простая эвристика для обнаружения возможных нарушений
                lower_pos = response_text.find(lower_act)
                higher_pos = response_text.find(higher_act)

                # Если есть слова, указывающие на приоритет низшего акта
                problematic_words = ['отменяет', 'заменяет', 'главнее', 'приоритет']
                surrounding_text = response_text[max(0, lower_pos-50):lower_pos+100]

                if any(word in surrounding_text for word in problematic_words):
                    issues.append(self.create_issue(
                        issue_id=f"hierarchy_violation_{len(issues)}",
                        category=ValidationCategory.LEGAL_CORRECTNESS,
                        severity=ValidationSeverity.HIGH,
                        title="Возможное нарушение иерархии норм",
                        description=violation_msg,
                        recommendations=["Проверить соотношение юридической силы актов", "Уточнить иерархию применения норм"],
                        affected_elements=[lower_act, higher_act]
                    ))

        return issues

    def _check_legal_actuality(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет актуальность правовых норм"""
        issues = []

        # Список типичных устаревших ссылок
        outdated_references = [
            'кодекс рсфср',
            'закон рсфср',
            'гк рсфср',
            'ук рсфср',
            'кзот',
            'основы законодательства ссср'
        ]

        response_text = " ".join(response.sections.values()).lower()

        for outdated_ref in outdated_references:
            if outdated_ref in response_text:
                issues.append(self.create_issue(
                    issue_id=f"actuality_outdated_{len(issues)}",
                    category=ValidationCategory.LEGAL_CORRECTNESS,
                    severity=ValidationSeverity.HIGH,
                    title="Устаревшая правовая ссылка",
                    description=f"Найдена ссылка на устаревший акт: {outdated_ref}",
                    recommendations=["Заменить на актуальную ссылку", "Проверить действующее законодательство"],
                    affected_elements=[outdated_ref]
                ))

        # Проверка на слишком старые даты в контексте действующего права
        import re
        old_years = re.findall(r'19[0-8]\d', response_text)
        for year in old_years:
            context_start = max(0, response_text.find(year) - 30)
            context_end = min(len(response_text), response_text.find(year) + 30)
            context = response_text[context_start:context_end]

            # Если старый год упоминается в контексте действующего права
            if any(word in context for word in ['действует', 'применяется', 'регулирует']):
                issues.append(self.create_issue(
                    issue_id=f"actuality_old_year_{year}",
                    category=ValidationCategory.LEGAL_CORRECTNESS,
                    severity=ValidationSeverity.MEDIUM,
                    title="Подозрительно старая дата",
                    description=f"Год {year} в контексте действующего права",
                    recommendations=["Проверить актуальность нормы", "Уточнить дату последней редакции"],
                    affected_elements=[year]
                ))

        return issues

    def _check_jurisdiction_scope(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет корректность указания юрисдикции"""
        issues = []

        # Поиск указаний на юрисдикцию
        response_text = " ".join(response.sections.values()).lower()

        # Проверка на смешение федерального и регионального права
        federal_indicators = ['федеральный', 'общероссийский', 'на территории рф', 'по всей россии']
        regional_indicators = ['региональный', 'субъект рф', 'местный', 'муниципальный']

        has_federal = any(indicator in response_text for indicator in federal_indicators)
        has_regional = any(indicator in response_text for indicator in regional_indicators)

        if has_federal and has_regional:
            # Проверяем, есть ли пояснения о разграничении
            explanation_indicators = ['отличается', 'может отличаться', 'в зависимости от региона', 'дополнительно']
            has_explanation = any(indicator in response_text for indicator in explanation_indicators)

            if not has_explanation:
                issues.append(self.create_issue(
                    issue_id="jurisdiction_mixed",
                    category=ValidationCategory.LEGAL_CORRECTNESS,
                    severity=ValidationSeverity.MEDIUM,
                    title="Смешение уровней юрисдикции без пояснений",
                    description="Одновременное упоминание федерального и регионального права без разъяснений",
                    recommendations=["Разделить федеральное и региональное регулирование", "Указать приоритет норм", "Добавить пояснения о разграничении компетенции"],
                    affected_elements=["указания на юрисдикцию"]
                ))

        # Проверка специфических юрисдикционных вопросов
        jurisdiction_conflicts = [
            ('налоговое право', ['местный', 'муниципальный'], 'Налоговое право преимущественно федеральное'),
            ('семейное право', ['региональный'], 'Семейное право регулируется федерально'),
            ('административные правонарушения', ['федеральный'], 'Есть региональные КоАП'),
        ]

        for law_area, wrong_indicators, explanation in jurisdiction_conflicts:
            if law_area in response_text:
                for indicator in wrong_indicators:
                    if indicator in response_text:
                        issues.append(self.create_issue(
                            issue_id=f"jurisdiction_conflict_{law_area}_{indicator}",
                            category=ValidationCategory.LEGAL_CORRECTNESS,
                            severity=ValidationSeverity.MEDIUM,
                            title="Некорректное указание юрисдикции",
                            description=f"{explanation}",
                            recommendations=["Уточнить уровень регулирования", "Проверить компетенцию уровней власти"],
                            affected_elements=[law_area, indicator]
                        ))

        return issues

    def _check_procedure_correctness(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет корректность процедурных указаний"""
        issues = []

        # Проверка процедурных инструкций
        practical_section = response.sections.get(ResponseSection.PRACTICAL_STEPS, '')

        if practical_section:
            # Проверка на слишком категоричные утверждения
            categorical_phrases = [
                'всегда подавайте',
                'никогда не делайте',
                'обязательно получите',
                'гарантированно решит',
                'в любом случае',
                'без исключений'
            ]

            for phrase in categorical_phrases:
                if phrase.lower() in practical_section.lower():
                    issues.append(self.create_issue(
                        issue_id=f"procedure_categorical_{len(issues)}",
                        category=ValidationCategory.LEGAL_CORRECTNESS,
                        severity=ValidationSeverity.MEDIUM,
                        title="Слишком категоричные утверждения",
                        description=f"Найдена категоричная формулировка: {phrase}",
                        recommendations=["Использовать более осторожные формулировки", "Добавить оговорки", "Указать возможные исключения"],
                        section=ResponseSection.PRACTICAL_STEPS,
                        affected_elements=[phrase]
                    ))

            # Проверка процедурных сроков
            import re
            time_patterns = [
                r'(\d+)\s*дней?',
                r'(\d+)\s*месяцев?',
                r'в течение\s+(\d+)',
                r'срок\s+(\d+)'
            ]

            for pattern in time_patterns:
                matches = re.findall(pattern, practical_section, re.IGNORECASE)
                for match in matches:
                    days = int(match)
                    # Проверка подозрительно коротких или длинных сроков
                    if days == 1:
                        issues.append(self.create_issue(
                            issue_id=f"procedure_short_term_{match}",
                            category=ValidationCategory.LEGAL_CORRECTNESS,
                            severity=ValidationSeverity.LOW,
                            title="Подозрительно короткий срок",
                            description=f"Срок {match} дней может быть слишком коротким",
                            recommendations=["Проверить корректность срока", "Уточнить в нормативном акте"],
                            affected_elements=[f"{match} дней"]
                        ))
                    elif days > 365:
                        issues.append(self.create_issue(
                            issue_id=f"procedure_long_term_{match}",
                            category=ValidationCategory.LEGAL_CORRECTNESS,
                            severity=ValidationSeverity.LOW,
                            title="Подозрительно длинный срок",
                            description=f"Срок {match} дней кажется слишком длинным",
                            recommendations=["Проверить корректность срока", "Возможно, имелся в виду иной период"],
                            affected_elements=[f"{match} дней"]
                        ))

        # Проверка на корректность указания инстанций
        response_text = " ".join(response.sections.values()).lower()

        procedure_mistakes = [
            ('подавайте в верховный суд', 'Верховный суд не первая инстанция для большинства дел'),
            ('обращайтесь в конституционный суд', 'КС РФ рассматривает только конституционные вопросы'),
            ('идите в арбитраж', 'Арбитражные суды для экономических споров между юрлицами'),
        ]

        for mistake_phrase, explanation in procedure_mistakes:
            if mistake_phrase in response_text:
                issues.append(self.create_issue(
                    issue_id=f"procedure_wrong_instance_{len(issues)}",
                    category=ValidationCategory.LEGAL_CORRECTNESS,
                    severity=ValidationSeverity.HIGH,
                    title="Некорректное указание судебной инстанции",
                    description=f"{explanation}",
                    recommendations=["Указать правильную инстанцию", "Проверить подсудность", "Уточнить процедуру обращения"],
                    affected_elements=[mistake_phrase]
                ))

        return issues