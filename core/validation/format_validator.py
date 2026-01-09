"""
Валидатор формальных требований.
Проверяет структуру ответа, форматирование и оформление цитат.
"""

import logging
from typing import Dict, List, Optional, Any

from .types import ValidationSeverity, ValidationCategory, ValidationIssue
from .base_validator import BaseValidator
from ..enhanced_response_generator import StructuredResponse, ResponseSection

logger = logging.getLogger(__name__)

class FormatValidator(BaseValidator):
    """
    Валидатор для проверки формальных требований к ответам.
    Проверяет структуру, форматирование и оформление ссылок.
    """

    async def validate_formal_requirements(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация формальных требований"""
        issues = []

        try:
            # Проверка структуры ответа
            structure_issues = self._check_response_structure(response)
            issues.extend(structure_issues)

            # Проверка форматирования
            formatting_issues = self._check_formatting(response)
            issues.extend(formatting_issues)

            # Проверка ссылок и цитат
            citation_issues = self._check_citations_format(response)
            issues.extend(citation_issues)

            # Проверка качества разметки
            markup_issues = self._check_markup_quality(response)
            issues.extend(markup_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке формальных требований: {e}")

        return issues

    def _check_response_structure(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет структуру ответа"""
        issues = []

        # Проверка логичности порядка секций
        section_order = list(response.sections.keys())

        # Summary должна быть первой, если присутствует
        if ResponseSection.SUMMARY in section_order and section_order[0] != ResponseSection.SUMMARY:
            issues.append(self.create_issue(
                issue_id="structure_summary_first",
                category=ValidationCategory.FORMAL_REQUIREMENTS,
                severity=ValidationSeverity.LOW,
                title="Неправильный порядок секций",
                description="Краткий ответ должен быть первым",
                recommendations=["Переставить секции в логическом порядке", "Начать с краткого ответа"],
                auto_fix_available=True,
                affected_elements=["порядок секций"]
            ))

        # Sources должны быть последними, если присутствуют
        if (ResponseSection.SOURCES in section_order and
            section_order.index(ResponseSection.SOURCES) != len(section_order) - 1):
            issues.append(self.create_issue(
                issue_id="structure_sources_last",
                category=ValidationCategory.FORMAL_REQUIREMENTS,
                severity=ValidationSeverity.LOW,
                title="Источники не в конце",
                description="Источники должны быть в конце ответа",
                recommendations=["Переместить источники в конец", "Завершать ответ списком источников"],
                auto_fix_available=True,
                affected_elements=["расположение источников"]
            ))

        # Проверка логичности последовательности секций
        expected_order = [
            ResponseSection.SUMMARY,
            ResponseSection.LEGAL_BASIS,
            ResponseSection.PRACTICAL_STEPS,
            ResponseSection.RISKS_WARNINGS,
            ResponseSection.SOURCES
        ]

        current_positions = {}
        for section in section_order:
            if section in expected_order:
                current_positions[section] = section_order.index(section)

        # Проверка нарушений ожидаемого порядка
        for i, section1 in enumerate(expected_order):
            if section1 not in current_positions:
                continue
            for section2 in expected_order[i+1:]:
                if section2 not in current_positions:
                    continue

                if current_positions[section1] > current_positions[section2]:
                    issues.append(self.create_issue(
                        issue_id=f"structure_order_{section1.value}_{section2.value}",
                        category=ValidationCategory.FORMAL_REQUIREMENTS,
                        severity=ValidationSeverity.LOW,
                        title="Нарушена логическая последовательность секций",
                        description=f"Секция {section2.value} должна следовать после {section1.value}",
                        recommendations=["Изменить порядок секций согласно логике изложения"],
                        auto_fix_available=True,
                        affected_elements=[section1.value, section2.value]
                    ))
                    break

        # Проверка наличия пустых секций
        for section, content in response.sections.items():
            if not content.strip():
                issues.append(self.create_issue(
                    issue_id=f"structure_empty_section_{section.value}",
                    category=ValidationCategory.FORMAL_REQUIREMENTS,
                    severity=ValidationSeverity.MEDIUM,
                    title="Пустая секция",
                    description=f"Секция {section.value} не содержит контента",
                    recommendations=["Заполнить секцию контентом", "Удалить пустую секцию"],
                    section=section,
                    affected_elements=[section.value]
                ))

        return issues

    def _check_formatting(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет форматирование"""
        issues = []

        for section, content in response.sections.items():
            # Проверка длины строк
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if len(line) > 120:  # Слишком длинная строка
                    issues.append(self.create_issue(
                        issue_id=f"formatting_long_line_{section.value}_{i}",
                        category=ValidationCategory.FORMAL_REQUIREMENTS,
                        severity=ValidationSeverity.LOW,
                        title="Слишком длинная строка",
                        description=f"Строка {i+1} в секции {section.value} превышает 120 символов ({len(line)} символов)",
                        recommendations=["Разбить на несколько строк", "Улучшить форматирование", "Использовать перенос строк"],
                        section=section,
                        affected_elements=[f"строка {i+1}"]
                    ))

            # Проверка избыточных пробелов и переносов
            formatting_issues = self._check_whitespace_issues(content, section)
            issues.extend(formatting_issues)

            # Проверка использования списков
            list_issues = self._check_list_formatting(content, section)
            issues.extend(list_issues)

            # Проверка заголовков и подзаголовков
            header_issues = self._check_header_formatting(content, section)
            issues.extend(header_issues)

        return issues

    def _check_citations_format(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет формат цитат и ссылок"""
        issues = []

        # Проверка единообразия ссылок
        if response.sources:
            citation_formats = set()
            citation_examples = {}

            for source in response.sources:
                title = source.get('title', '')
                if title:
                    # Определяем формат ссылки
                    if title.startswith('Федеральный закон'):
                        format_type = 'federal_law'
                        citation_formats.add(format_type)
                        citation_examples[format_type] = title[:50] + "..."
                    elif 'кодекс' in title.lower():
                        format_type = 'codex'
                        citation_formats.add(format_type)
                        citation_examples[format_type] = title[:50] + "..."
                    elif 'конституция' in title.lower():
                        format_type = 'constitution'
                        citation_formats.add(format_type)
                        citation_examples[format_type] = title[:50] + "..."
                    elif 'постановление' in title.lower():
                        format_type = 'resolution'
                        citation_formats.add(format_type)
                        citation_examples[format_type] = title[:50] + "..."

            # Если форматы разные, рекомендуем унификацию
            if len(citation_formats) > 2:  # Более 2 разных форматов
                issues.append(self.create_issue(
                    issue_id="citations_inconsistent",
                    category=ValidationCategory.FORMAL_REQUIREMENTS,
                    severity=ValidationSeverity.LOW,
                    title="Непоследовательное оформление ссылок",
                    description=f"Используется {len(citation_formats)} разных форматов оформления правовых актов",
                    recommendations=["Унифицировать формат ссылок", "Следовать единому стандарту", "Использовать один стиль цитирования"],
                    affected_elements=["формат ссылок"]
                ))

            # Проверка полноты информации об источниках
            for i, source in enumerate(response.sources):
                missing_fields = []

                if not source.get('title'):
                    missing_fields.append('название')
                if not source.get('type'):
                    missing_fields.append('тип документа')
                if not source.get('date') and not source.get('number'):
                    missing_fields.append('дата или номер')

                if missing_fields:
                    issues.append(self.create_issue(
                        issue_id=f"citations_incomplete_{i}",
                        category=ValidationCategory.FORMAL_REQUIREMENTS,
                        severity=ValidationSeverity.MEDIUM,
                        title="Неполная информация об источнике",
                        description=f"Источник {i+1}: отсутствует {', '.join(missing_fields)}",
                        recommendations=["Дополнить информацию об источнике", "Указать все обязательные поля"],
                        affected_elements=[f"источник {i+1}"]
                    ))

        # Проверка ссылок в тексте
        for section, content in response.sections.items():
            citation_issues = self._check_inline_citations(content, section)
            issues.extend(citation_issues)

        return issues

    def _check_markup_quality(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверяет качество разметки и форматирования"""
        issues = []

        for section, content in response.sections.items():
            # Проверка использования выделения текста
            markup_issues = self._analyze_text_markup(content, section)
            issues.extend(markup_issues)

            # Проверка структурированности контента
            structure_issues = self._check_content_structure(content, section)
            issues.extend(structure_issues)

        return issues

    def _check_whitespace_issues(self, content: str, section: ResponseSection) -> List[ValidationIssue]:
        """Проверяет проблемы с пробелами и переносами"""
        issues = []

        # Проверка множественных пробелов
        if '  ' in content:  # Два и более пробела подряд
            issues.append(self.create_issue(
                issue_id=f"formatting_multiple_spaces_{section.value}",
                category=ValidationCategory.FORMAL_REQUIREMENTS,
                severity=ValidationSeverity.LOW,
                title="Множественные пробелы",
                description=f"В секции {section.value} обнаружены множественные пробелы",
                recommendations=["Удалить лишние пробелы", "Использовать один пробел между словами"],
                section=section,
                auto_fix_available=True,
                affected_elements=["форматирование пробелов"]
            ))

        # Проверка пробелов в конце строк
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.endswith(' '):
                issues.append(self.create_issue(
                    issue_id=f"formatting_trailing_spaces_{section.value}_{i}",
                    category=ValidationCategory.FORMAL_REQUIREMENTS,
                    severity=ValidationSeverity.LOW,
                    title="Пробелы в конце строки",
                    description=f"Строка {i+1} в секции {section.value} заканчивается пробелом",
                    recommendations=["Удалить завершающие пробелы"],
                    section=section,
                    auto_fix_available=True,
                    affected_elements=[f"строка {i+1}"]
                ))

        # Проверка избыточных переносов строк
        if '\n\n\n' in content:  # Три и более переноса подряд
            issues.append(self.create_issue(
                issue_id=f"formatting_excessive_newlines_{section.value}",
                category=ValidationCategory.FORMAL_REQUIREMENTS,
                severity=ValidationSeverity.LOW,
                title="Избыточные переносы строк",
                description=f"В секции {section.value} слишком много переносов строк подряд",
                recommendations=["Использовать максимум двойной перенос", "Улучшить структуру абзацев"],
                section=section,
                auto_fix_available=True,
                affected_elements=["переносы строк"]
            ))

        return issues

    def _check_list_formatting(self, content: str, section: ResponseSection) -> List[ValidationIssue]:
        """Проверяет форматирование списков"""
        issues = []

        lines = content.split('\n')

        # Поиск списков
        list_markers = ['-', '•', '*', '1.', '2.', '3.']
        list_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if any(stripped.startswith(marker) for marker in list_markers):
                list_lines.append(i)

        if len(list_lines) >= 2:  # Есть список
            # Проверка единообразия маркеров
            markers_used = set()
            for line_num in list_lines:
                line = lines[line_num].strip()
                for marker in list_markers:
                    if line.startswith(marker):
                        markers_used.add(marker[0])  # Берем первый символ
                        break

            if len(markers_used) > 1:
                issues.append(self.create_issue(
                    issue_id=f"formatting_mixed_list_markers_{section.value}",
                    category=ValidationCategory.FORMAL_REQUIREMENTS,
                    severity=ValidationSeverity.LOW,
                    title="Смешанные маркеры списка",
                    description=f"В секции {section.value} используются разные маркеры списка: {', '.join(markers_used)}",
                    recommendations=["Использовать единообразные маркеры", "Выбрать один стиль списка"],
                    section=section,
                    affected_elements=["маркеры списка"]
                ))

        return issues

    def _check_header_formatting(self, content: str, section: ResponseSection) -> List[ValidationIssue]:
        """Проверяет форматирование заголовков"""
        issues = []

        lines = content.split('\n')

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Поиск потенциальных заголовков (строки заглавными буквами)
            if (len(stripped) > 10 and
                stripped.isupper() and
                not any(char in stripped for char in '.,!?')):  # Не предложения

                issues.append(self.create_issue(
                    issue_id=f"formatting_caps_header_{section.value}_{i}",
                    category=ValidationCategory.FORMAL_REQUIREMENTS,
                    severity=ValidationSeverity.LOW,
                    title="Заголовок заглавными буквами",
                    description=f"Строка {i+1} в секции {section.value} полностью заглавными: '{stripped[:30]}...'",
                    recommendations=["Использовать нормальный регистр", "Применить выделение жирным шрифтом"],
                    section=section,
                    affected_elements=[f"заголовок строка {i+1}"]
                ))

        return issues

    def _check_inline_citations(self, content: str, section: ResponseSection) -> List[ValidationIssue]:
        """Проверяет ссылки внутри текста"""
        issues = []

        import re

        # Поиск ссылок на статьи и законы
        citation_patterns = [
            r'ст\.\s*\d+',
            r'статья\s+\d+',
            r'ч\.\s*\d+\s+ст\.\s*\d+',
            r'п\.\s*\d+\s+ст\.\s*\d+',
        ]

        for pattern in citation_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                # Проверка наличия названия закона рядом с ссылкой
                match_pos = content.lower().find(match.lower())
                surrounding = content[max(0, match_pos-100):match_pos+100].lower()

                law_indicators = ['федеральный закон', 'кодекс', 'конституция']
                has_law_reference = any(indicator in surrounding for indicator in law_indicators)

                if not has_law_reference:
                    issues.append(self.create_issue(
                        issue_id=f"citations_incomplete_reference_{section.value}",
                        category=ValidationCategory.FORMAL_REQUIREMENTS,
                        severity=ValidationSeverity.MEDIUM,
                        title="Неполная ссылка на норму",
                        description=f"Ссылка '{match}' без указания названия закона",
                        recommendations=["Указать название нормативного акта", "Дать полную ссылку на норму"],
                        section=section,
                        affected_elements=[match]
                    ))

        return issues

    def _analyze_text_markup(self, content: str, section: ResponseSection) -> List[ValidationIssue]:
        """Анализирует использование разметки текста"""
        issues = []

        # Проверка на отсутствие выделения важных терминов
        important_terms = ['важно', 'внимание', 'обязательно', 'запрещено', 'необходимо']

        for term in important_terms:
            if term.lower() in content.lower():
                # Проверяем, выделен ли термин
                if (f'**{term}**' not in content.lower() and
                    f'*{term}*' not in content.lower() and
                    term.upper() not in content):

                    issues.append(self.create_issue(
                        issue_id=f"markup_important_term_{section.value}_{term}",
                        category=ValidationCategory.FORMAL_REQUIREMENTS,
                        severity=ValidationSeverity.LOW,
                        title="Важный термин не выделен",
                        description=f"Важный термин '{term}' в секции {section.value} не выделен",
                        recommendations=["Выделить важные термины жирным", "Использовать курсив для акцентов"],
                        section=section,
                        affected_elements=[term]
                    ))

        return issues

    def _check_content_structure(self, content: str, section: ResponseSection) -> List[ValidationIssue]:
        """Проверяет структурированность контента"""
        issues = []

        # Проверка длинных параграфов без структуры
        paragraphs = content.split('\n\n')

        for i, paragraph in enumerate(paragraphs):
            if len(paragraph) > 500 and paragraph.count('.') > 5:  # Длинный параграф с множеством предложений
                # Проверяем, есть ли внутренняя структура
                has_structure = (
                    any(marker in paragraph for marker in ['-', '•', '1.', '2.']) or
                    paragraph.count('\n') > 2
                )

                if not has_structure:
                    issues.append(self.create_issue(
                        issue_id=f"structure_long_paragraph_{section.value}_{i}",
                        category=ValidationCategory.FORMAL_REQUIREMENTS,
                        severity=ValidationSeverity.MEDIUM,
                        title="Длинный неструктурированный параграф",
                        description=f"Параграф {i+1} в секции {section.value} слишком длинный ({len(paragraph)} символов) и неструктурированный",
                        recommendations=["Разбить на более короткие абзацы", "Добавить списки или подпункты", "Улучшить структуру изложения"],
                        section=section,
                        affected_elements=[f"параграф {i+1}"]
                    ))

        return issues