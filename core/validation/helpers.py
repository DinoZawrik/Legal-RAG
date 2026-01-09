"""Validation helper functions (Context7 validated)."""

from __future__ import annotations
import logging
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List
from datetime import datetime

from .models import ValidationCategory, ValidationIssue, ValidationReport, ValidationSeverity

if TYPE_CHECKING:
    from ..enhanced_response_generator import ResponseQuality, ResponseSection, StructuredResponse

logger = logging.getLogger(__name__)

def extract_legal_references(validator, response: 'StructuredResponse') -> List[str]:
    """Извлекает правовые ссылки из ответа"""
    references = []
    response_text = " ".join(response.sections.values())

    patterns = validator.validation_rules[ValidationCategory.FACTUAL_ACCURACY]['reference_patterns']

    for pattern in patterns:
        matches = re.findall(pattern, response_text, re.IGNORECASE)
        references.extend(matches)

    return list(set(references))  # Убираем дубликаты


def verify_legal_reference(validator, reference: str,
                          search_results: List[Dict[str, Any]] = None) -> bool:
    """Проверяет существование правовой ссылки"""
    if not search_results:
        return True  # Не можем проверить без исходных данных

    # Поиск ссылки в исходных документах
    ref_lower = reference.lower()

    for result in search_results:
        content = result.get('content', '').lower()
        metadata = result.get('metadata', {})

        if ref_lower in content or ref_lower in str(metadata).lower():
            return True

    return False


def validate_dates_and_periods(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет корректность дат и временных периодов"""
    issues = []
    date_patterns = [r'\d{1,2}\.\d{1,2}\.\d{4}', r'\d{4}\s*год[ау]?', r'с\s+\d{4}\s*года', r'до\s+\d{4}\s*года']
    response_text = " ".join(response.sections.values())
    for pattern in date_patterns:
        for match in re.findall(pattern, response_text):
            if '2025' in match or '2026' in match:
                issues.append(ValidationIssue(
                    issue_id=f"date_future_{len(issues)}", category=ValidationCategory.FACTUAL_ACCURACY,
                    severity=ValidationSeverity.MEDIUM, title="Подозрительная дата",
                    description=f"Найдена дата в будущем: {match}",
                    recommendations=["Проверить корректность даты"], affected_elements=[match]))
    return issues


def validate_numeric_data(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет корректность числовых данных"""
    issues = []
    response_text = " ".join(response.sections.values())
    penalty_patterns = [r'штраф\s+(\d+(?:\s?\d+)*)\s*рублей?', r'санкция\s+(\d+(?:\s?\d+)*)\s*рублей?',
                       r'взыскание\s+(\d+(?:\s?\d+)*)\s*рублей?']
    for pattern in penalty_patterns:
        for match in re.findall(pattern, response_text, re.IGNORECASE):
            amount = int(match.replace(' ', ''))
            if amount > 10000000:
                issues.append(ValidationIssue(
                    issue_id=f"numeric_suspicious_{len(issues)}", category=ValidationCategory.FACTUAL_ACCURACY,
                    severity=ValidationSeverity.MEDIUM, title="Подозрительная сумма",
                    description=f"Очень большая сумма: {amount:,} рублей",
                    recommendations=["Проверить корректность суммы", "Уточнить источник данных"],
                    affected_elements=[f"{amount:,} рублей"]))
    return issues


def check_legal_hierarchy(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет соблюдение иерархии правовых актов"""
    issues = []
    if response.sources:
        for i, source in enumerate(response.sources):
            for j, other_source in enumerate(response.sources[i+1:], i+1):
                if 'федеральный закон' in source.get('type', '').lower() and 'конституция' in other_source.get('type', '').lower():
                    issues.append(ValidationIssue(
                        issue_id=f"hierarchy_order_{i}_{j}", category=ValidationCategory.LEGAL_CORRECTNESS,
                        severity=ValidationSeverity.MEDIUM, title="Нарушение иерархии актов",
                        description="Конституция должна упоминаться раньше федеральных законов",
                        recommendations=["Изменить порядок источников", "Указать иерархию юридической силы"],
                        affected_elements=[source.get('title', ''), other_source.get('title', '')]))
    return issues

def check_legal_actuality(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет актуальность правовых норм"""
    issues = []
    outdated_references = ['кодекс рсфср', 'закон рсфср', 'гк рсфср', 'ук рсфср']
    response_text = " ".join(response.sections.values()).lower()
    for outdated_ref in outdated_references:
        if outdated_ref in response_text:
            issues.append(ValidationIssue(
                issue_id=f"actuality_outdated_{len(issues)}", category=ValidationCategory.LEGAL_CORRECTNESS,
                severity=ValidationSeverity.HIGH, title="Устаревшая правовая ссылка",
                description=f"Найдена ссылка на устаревший акт: {outdated_ref}",
                recommendations=["Заменить на актуальную ссылку", "Проверить действующее законодательство"],
                affected_elements=[outdated_ref]))
    return issues

def check_jurisdiction_scope(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет корректность указания юрисдикции"""
    issues = []
    response_text = " ".join(response.sections.values()).lower()
    federal_indicators = ['федеральный', 'общероссийский', 'на территории рф']
    regional_indicators = ['региональный', 'субъект рф', 'местный']
    has_federal = any(i in response_text for i in federal_indicators)
    has_regional = any(i in response_text for i in regional_indicators)
    if has_federal and has_regional:
        issues.append(ValidationIssue(
            issue_id="jurisdiction_mixed", category=ValidationCategory.LEGAL_CORRECTNESS,
            severity=ValidationSeverity.MEDIUM, title="Смешение уровней юрисдикции",
            description="Одновременное упоминание федерального и регионального права без пояснений",
            recommendations=["Разделить федеральное и региональное регулирование", "Указать приоритет норм"],
            affected_elements=["указания на юрисдикцию"]))
    return issues


def check_procedure_correctness(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет корректность процедурных указаний"""
    issues = []

    # Import ResponseSection here to avoid circular import
    from ..enhanced_response_generator import ResponseSection

    # Поиск процедурных инструкций
    practical_section = response.sections.get(ResponseSection.PRACTICAL_STEPS, '')

    if practical_section:
        # Проверка на слишком категоричные утверждения
        categorical_phrases = [
            'всегда подавайте',
            'никогда не делайте',
            'обязательно получите',
            'гарантированно решит'
        ]

        for phrase in categorical_phrases:
            if phrase.lower() in practical_section.lower():
                issues.append(ValidationIssue(
                    issue_id=f"procedure_categorical_{len(issues)}",
                    category=ValidationCategory.LEGAL_CORRECTNESS,
                    severity=ValidationSeverity.MEDIUM,
                    title="Слишком категоричные утверждения",
                    description=f"Найдена категоричная формулировка: {phrase}",
                    recommendations=["Использовать более осторожные формулировки", "Добавить оговорки"],
                    section=ResponseSection.PRACTICAL_STEPS,
                    affected_elements=[phrase]
                ))

    return issues


def validate_inference_logic(validator, inference) -> bool:
    """Проверяет логическую корректность вывода"""
    # Упрощенная проверка логики
    if not hasattr(inference, 'logical_chain') or not inference.logical_chain:
        return False

    # Проверка минимальной длины логической цепи
    if len(inference.logical_chain) < 2:
        return False

    # Проверка связности шагов (базовая)
    return True


def find_internal_contradictions(validator, response: 'StructuredResponse') -> List[Dict[str, str]]:
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

    # Поиск противоречивых утверждений (упрощенная логика)
    contradiction_pairs = [
        (['обязан', 'должен'], ['не обязан', 'не должен']),
        (['разрешено', 'можно'], ['запрещено', 'нельзя']),
        (['всегда'], ['никогда']),
        (['требуется'], ['не требуется'])
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
                            'statement1': stmt1['text'][:100] + "...",
                            'statement2': stmt2['text'][:100] + "...",
                            'section1': stmt1['section'].value,
                            'section2': stmt2['section'].value
                        })

    return contradictions


# ============================================================================
# USER ADAPTATION FUNCTIONS
# ============================================================================

def check_language_complexity(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет соответствие языка уровню пользователя"""
    from ..smart_query_classifier import UserExpertiseLevel
    issues = []
    response_text = " ".join(response.sections.values())
    complex_terms = sum(1 for term in validator.legal_terms_dictionary if term in response_text.lower())
    if response.user_expertise == UserExpertiseLevel.BEGINNER and complex_terms > 5:
        issues.append(ValidationIssue(
            issue_id="language_too_complex", category=ValidationCategory.USER_ADAPTATION,
            severity=ValidationSeverity.MEDIUM, title="Язык слишком сложен для начинающего",
            description=f"Найдено {complex_terms} сложных правовых терминов",
            recommendations=["Упростить язык", "Добавить объяснения терминов"],
            affected_elements=["общая сложность языка"]))
    elif response.user_expertise == UserExpertiseLevel.EXPERT and complex_terms < 2:
        issues.append(ValidationIssue(
            issue_id="language_too_simple", category=ValidationCategory.USER_ADAPTATION,
            severity=ValidationSeverity.LOW, title="Язык слишком прост для эксперта",
            description="Недостаточно профессиональной терминологии",
            recommendations=["Добавить профессиональные термины", "Углубить анализ"],
            affected_elements=["уровень профессионализма языка"]))
    return issues

def check_terminology_explanation(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет объяснение терминологии"""
    from ..smart_query_classifier import UserExpertiseLevel
    issues = []
    if response.user_expertise == UserExpertiseLevel.BEGINNER:
        response_text = " ".join(response.sections.values()).lower()
        unexplained = []
        for term in list(validator.legal_terms_dictionary)[:10]:
            if term in response_text:
                idx = response_text.find(term)
                surrounding = response_text[max(0, idx-50):idx+100]
                if not any(ind in surrounding for ind in ['это означает', 'то есть', '(', 'называется']):
                    unexplained.append(term)
        if unexplained:
            issues.append(ValidationIssue(
                issue_id="terminology_unexplained", category=ValidationCategory.USER_ADAPTATION,
                severity=ValidationSeverity.MEDIUM, title="Необъясненные термины",
                description=f"Термины без объяснений: {', '.join(unexplained[:3])}",
                recommendations=["Добавить объяснения терминов", "Использовать простые синонимы"],
                affected_elements=unexplained))
    return issues

def check_practical_guidance(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет наличие практических рекомендаций"""
    from ..enhanced_response_generator import ResponseSection
    from ..smart_query_classifier import UserExpertiseLevel
    issues = []
    if not response.sections.get(ResponseSection.PRACTICAL_STEPS) and response.user_expertise in [UserExpertiseLevel.BEGINNER, UserExpertiseLevel.INTERMEDIATE]:
        issues.append(ValidationIssue(
            issue_id="practical_missing", category=ValidationCategory.USER_ADAPTATION,
            severity=ValidationSeverity.MEDIUM, title="Отсутствуют практические рекомендации",
            description="Для данного уровня пользователя нужны практические советы",
            recommendations=["Добавить секцию с практическими шагами", "Указать конкретные действия"],
            auto_fix_available=True, affected_elements=["практические рекомендации"]))
    return issues


# ============================================================================
# FORMAL CHECK FUNCTIONS
# ============================================================================

def check_response_structure(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет структуру ответа"""
    from ..enhanced_response_generator import ResponseSection
    issues = []
    section_order = list(response.sections.keys())
    if section_order and section_order[0] != ResponseSection.SUMMARY:
        issues.append(ValidationIssue(
            issue_id="structure_summary_first", category=ValidationCategory.FORMAL_REQUIREMENTS,
            severity=ValidationSeverity.LOW, title="Неправильный порядок секций",
            description="Краткий ответ должен быть первым",
            recommendations=["Переставить секции в логическом порядке"],
            auto_fix_available=True, affected_elements=["порядок секций"]))
    if ResponseSection.SOURCES in section_order and section_order[-1] != ResponseSection.SOURCES:
        issues.append(ValidationIssue(
            issue_id="structure_sources_last", category=ValidationCategory.FORMAL_REQUIREMENTS,
            severity=ValidationSeverity.LOW, title="Источники не в конце",
            description="Источники должны быть в конце ответа",
            recommendations=["Переместить источники в конец"],
            auto_fix_available=True, affected_elements=["расположение источников"]))
    return issues

def check_formatting(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет форматирование"""
    issues = []
    for section, content in response.sections.items():
        for i, line in enumerate(content.split('\n')):
            if len(line) > 120:
                issues.append(ValidationIssue(
                    issue_id=f"formatting_long_line_{section.value}_{i}",
                    category=ValidationCategory.FORMAL_REQUIREMENTS, severity=ValidationSeverity.LOW,
                    title="Слишком длинная строка",
                    description=f"Строка {i+1} в секции {section.value} превышает 120 символов",
                    recommendations=["Разбить на несколько строк", "Улучшить форматирование"],
                    section=section, affected_elements=[f"строка {i+1}"]))
    return issues

def check_citations_format(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет формат цитат и ссылок"""
    issues = []
    if response.sources:
        formats = set()
        for source in response.sources:
            title = source.get('title', '')
            if title:
                if title.startswith('Федеральный закон'):
                    formats.add('federal_law')
                elif 'кодекс' in title.lower():
                    formats.add('codex')
                elif 'конституция' in title.lower():
                    formats.add('constitution')
        if len(formats) > 1:
            issues.append(ValidationIssue(
                issue_id="citations_inconsistent", category=ValidationCategory.FORMAL_REQUIREMENTS,
                severity=ValidationSeverity.LOW, title="Непоследовательное оформление ссылок",
                description="Разные форматы оформления правовых актов",
                recommendations=["Унифицировать формат ссылок", "Следовать единому стандарту"],
                affected_elements=["формат ссылок"]))
    return issues


# ============================================================================
# SAFETY CHECK FUNCTIONS
# ============================================================================

def check_disclaimers(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет наличие дисклеймеров"""
    issues = []
    response_text = " ".join(response.sections.values()).lower()
    required = ['консультация носит информационный характер', 'рекомендуется получить персональную консультацию',
                'для принятия решений обратитесь к специалисту']
    if not any(d in response_text for d in required):
        issues.append(ValidationIssue(
            issue_id="safety_no_disclaimer", category=ValidationCategory.SAFETY, severity=ValidationSeverity.HIGH,
            title="Отсутствует дисклеймер", description="Нет предупреждения об информационном характере консультации",
            recommendations=["Добавить дисклеймер", "Предупредить о необходимости персональной консультации"],
            auto_fix_available=True, affected_elements=["дисклеймер"]))
    return issues

def check_risk_warnings(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет предупреждения о рисках"""
    from ..enhanced_response_generator import ResponseSection
    issues = []
    if not response.sections.get(ResponseSection.RISKS_WARNINGS):
        issues.append(ValidationIssue(
            issue_id="safety_no_risks", category=ValidationCategory.SAFETY, severity=ValidationSeverity.MEDIUM,
            title="Отсутствуют предупреждения о рисках", description="Нет секции с предупреждениями о возможных рисках",
            recommendations=["Добавить предупреждения о рисках", "Указать возможные последствия"],
            auto_fix_available=True, affected_elements=["предупреждения о рисках"]))
    return issues

def check_dangerous_advice(validator, response: 'StructuredResponse') -> List[ValidationIssue]:
    """Проверяет на опасные советы"""
    issues = []
    response_text = " ".join(response.sections.values()).lower()
    for phrase in validator.safety_keywords['dangerous_advice']:
        if phrase.lower() in response_text:
            issues.append(ValidationIssue(
                issue_id=f"safety_dangerous_{len(issues)}", category=ValidationCategory.SAFETY,
                severity=ValidationSeverity.CRITICAL, title="Потенциально опасный совет",
                description=f"Найдена опасная формулировка: {phrase}",
                recommendations=["Смягчить формулировку", "Добавить оговорки", "Указать на риски"],
                affected_elements=[phrase]))
    return issues


# ============================================================================
# SCORING & REPORTING FUNCTIONS
# ============================================================================

def group_issues_by_category(issues: List[ValidationIssue]) -> Dict[ValidationCategory, List[ValidationIssue]]:
    """Группирует проблемы по категориям"""
    grouped = defaultdict(list)
    for issue in issues:
        grouped[issue.category].append(issue)
    return dict(grouped)

def group_issues_by_severity(issues: List[ValidationIssue]) -> Dict[ValidationSeverity, List[ValidationIssue]]:
    """Группирует проблемы по серьезности"""
    grouped = defaultdict(list)
    for issue in issues:
        grouped[issue.severity].append(issue)
    return dict(grouped)


def calculate_overall_score(validator, issues: List[ValidationIssue],
                           response: 'StructuredResponse') -> float:
    """Рассчитывает общую оценку качества"""
    base_score = 1.0
    severity_weights = {ValidationSeverity.CRITICAL: 0.3, ValidationSeverity.HIGH: 0.15,
                       ValidationSeverity.MEDIUM: 0.05, ValidationSeverity.LOW: 0.02, ValidationSeverity.INFO: 0.0}
    for issue in issues:
        base_score -= severity_weights.get(issue.severity, 0.1)
    if len(response.sections) >= 4:
        base_score += 0.05
    if len(response.sources) >= 3:
        base_score += 0.05
    if response.follow_up_questions:
        base_score += 0.03
    return max(0.0, min(1.0, base_score))


def determine_quality_grade(validator, score: float) -> 'ResponseQuality':
    """Определяет оценку качества"""
    # Import ResponseQuality here to avoid circular import
    from ..enhanced_response_generator import ResponseQuality

    if score >= validator.quality_thresholds['excellent']:
        return ResponseQuality.EXCELLENT
    elif score >= validator.quality_thresholds['good']:
        return ResponseQuality.GOOD
    elif score >= validator.quality_thresholds['acceptable']:
        return ResponseQuality.ACCEPTABLE
    else:
        return ResponseQuality.POOR


def generate_priority_fixes(issues: List[ValidationIssue]) -> List[str]:
    """Генерирует приоритетные исправления"""
    fixes = []
    for issue in [i for i in issues if i.severity == ValidationSeverity.CRITICAL][:3]:
        fixes.append(f"[CRITICAL] {issue.title}")
    for issue in [i for i in issues if i.severity == ValidationSeverity.HIGH][:2]:
        fixes.append(f"[HIGH] {issue.title}")
    for issue in [i for i in issues if i.auto_fix_available][:2]:
        fixes.append(f"[AUTO-FIX] {issue.title}")
    return fixes


def generate_improvement_suggestions(issues: List[ValidationIssue],
                                    response: 'StructuredResponse') -> List[str]:
    """Генерирует предложения по улучшению"""
    suggestions = []
    category_counts = defaultdict(int)
    for issue in issues:
        category_counts[issue.category] += 1

    if category_counts[ValidationCategory.COMPLETENESS] >= 2:
        suggestions.append("Добавить более детальный анализ и дополнительные секции")
    if category_counts[ValidationCategory.USER_ADAPTATION] >= 2:
        suggestions.append("Лучше адаптировать язык и структуру к уровню пользователя")
    if category_counts[ValidationCategory.SAFETY] >= 1:
        suggestions.append("Усилить предупреждения о рисках и добавить дисклеймеры")
    if category_counts[ValidationCategory.FACTUAL_ACCURACY] >= 1:
        suggestions.append("Проверить и дополнить правовые ссылки")
    if len(response.sources) < 3:
        suggestions.append("Добавить больше источников для подтверждения выводов")
    if not response.follow_up_questions:
        suggestions.append("Добавить уточняющие вопросы для углубления анализа")
    return suggestions[:5]


def create_error_report(response_id: str, error_message: str) -> ValidationReport:
    """Создает отчет об ошибке валидации"""
    # Import ResponseQuality here to avoid circular import
    from datetime import datetime
    from ..enhanced_response_generator import ResponseQuality

    return ValidationReport(
        response_id=response_id,
        timestamp=datetime.now(),
        overall_score=0.0,
        quality_grade=ResponseQuality.POOR,
        total_issues=1,
        critical_issues=1,
        priority_fixes=[f"[ERROR] {error_message}"],
        improvement_suggestions=["Исправить техническую ошибку системы валидации"]
    )


def format_validation_report(report: ValidationReport, detailed: bool = True) -> str:
    """Форматирует отчет валидации для вывода"""
    parts = [
        f"# ОТЧЕТ ВАЛИДАЦИИ КАЧЕСТВА",
        f"**ID ответа:** {report.response_id}",
        f"**Общая оценка:** {report.overall_score:.2f} ({report.quality_grade.value})",
        f"**Найдено проблем:** {report.total_issues} (критических: {report.critical_issues})"
    ]

    if report.priority_fixes:
        parts.append("\n## ПРИОРИТЕТНЫЕ ИСПРАВЛЕНИЯ:")
        parts.extend(f"* {fix}" for fix in report.priority_fixes)

    if detailed and report.issues_by_category:
        parts.append("\n## ДЕТАЛЬНЫЙ АНАЛИЗ:")
        severity_map = {
            ValidationSeverity.CRITICAL: "[CRITICAL]", ValidationSeverity.HIGH: "[HIGH]",
            ValidationSeverity.MEDIUM: "[MEDIUM]", ValidationSeverity.LOW: "[LOW]",
            ValidationSeverity.INFO: "[INFO]"
        }
        for category, issues in report.issues_by_category.items():
            if issues:
                parts.append(f"\n### {category.value.upper()}:")
                for issue in issues[:3]:
                    marker = severity_map.get(issue.severity, "[?]")
                    parts.append(f"{marker} **{issue.title}**\n   {issue.description}")
                    if issue.recommendations:
                        parts.append(f"   *Рекомендация: {issue.recommendations[0]}*")

    if report.improvement_suggestions:
        parts.append("\n## ПРЕДЛОЖЕНИЯ ПО УЛУЧШЕНИЮ:")
        parts.extend(f"* {s}" for s in report.improvement_suggestions)

    return "\n".join(parts)


__all__ = [
    # Fact checking
    "extract_legal_references",
    "verify_legal_reference",
    "validate_dates_and_periods",
    "validate_numeric_data",
    "check_legal_hierarchy",
    "check_legal_actuality",
    "check_jurisdiction_scope",
    "check_procedure_correctness",
    "validate_inference_logic",
    "find_internal_contradictions",
    # User adaptation
    "check_language_complexity",
    "check_terminology_explanation",
    "check_practical_guidance",
    # Formal checks
    "check_response_structure",
    "check_formatting",
    "check_citations_format",
    # Safety checks
    "check_disclaimers",
    "check_risk_warnings",
    "check_dangerous_advice",
    # Scoring & reporting
    "group_issues_by_category",
    "group_issues_by_severity",
    "calculate_overall_score",
    "determine_quality_grade",
    "generate_priority_fixes",
    "generate_improvement_suggestions",
    "create_error_report",
    "format_validation_report",
]
