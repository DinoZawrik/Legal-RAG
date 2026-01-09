"""
Валидатор безопасности для проверки рисков и опасных советов.
"""

import logging
from typing import List
import re

from .types import ValidationIssue, ValidationCategory, ValidationSeverity
from .base_validator import BaseValidator
from ..enhanced_response_generator import StructuredResponse

logger = logging.getLogger(__name__)

class SafetyValidator(BaseValidator):
    """Валидатор безопасности правовых консультаций"""

    async def validate_safety(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Валидация безопасности советов"""
        issues = []

        try:
            # Проверка дисклеймеров
            disclaimer_issues = self._check_disclaimers(response)
            issues.extend(disclaimer_issues)

            # Проверка предупреждений о рисках
            risk_issues = self._check_risk_warnings(response)
            issues.extend(risk_issues)

            # Проверка опасных советов
            dangerous_issues = self._check_dangerous_advice(response)
            issues.extend(dangerous_issues)

        except Exception as e:
            logger.error(f"Ошибка при проверке безопасности: {e}")

        return issues

    def _check_disclaimers(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверка наличия необходимых дисклеймеров"""
        issues = []

        # Получение полного текста ответа
        full_text = " ".join(response.sections.values())
        full_text_lower = full_text.lower()

        # Проверка триггерных слов, требующих дисклеймера
        disclaimer_needed = False
        for trigger in self.safety_keywords['disclaimer_triggers']:
            if trigger.lower() in full_text_lower:
                disclaimer_needed = True
                break

        if disclaimer_needed:
            # Проверка наличия дисклеймера
            disclaimer_phrases = [
                'рекомендуется обратиться к специалисту',
                'консультация с юристом',
                'данная информация носит ознакомительный характер',
                'не является юридической консультацией',
                'может потребоваться профессиональная помощь'
            ]

            has_disclaimer = any(phrase in full_text_lower for phrase in disclaimer_phrases)

            if not has_disclaimer:
                issues.append(ValidationIssue(
                    issue_id=self._generate_issue_id(ValidationCategory.SAFETY, "missing_disclaimer"),
                    category=ValidationCategory.SAFETY,
                    severity=ValidationSeverity.HIGH,
                    title="Отсутствует необходимый дисклеймер",
                    description="Ответ содержит рекомендации, но не содержит предупреждения о необходимости профессиональной консультации",
                    suggestions=[
                        "Добавить дисклеймер о рекомендации обратиться к специалисту",
                        "Указать, что информация носит ознакомительный характер",
                        "Предупредить о необходимости профессиональной юридической помощи"
                    ]
                ))

        return issues

    def _check_risk_warnings(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверка предупреждений о рисках"""
        issues = []

        full_text = " ".join(response.sections.values())
        full_text_lower = full_text.lower()

        # Поиск упоминаний рисков
        risk_mentions = []
        for risk_word in self.safety_keywords['risk_indicators']:
            if risk_word.lower() in full_text_lower:
                risk_mentions.append(risk_word)

        if risk_mentions:
            # Проверка наличия предупреждений
            warning_phrases = [
                'внимание', 'осторожно', 'предупреждение',
                'может привести к', 'чревато', 'опасно'
            ]

            has_warnings = any(phrase in full_text_lower for phrase in warning_phrases)

            if not has_warnings and len(risk_mentions) > 2:
                issues.append(ValidationIssue(
                    issue_id=self._generate_issue_id(ValidationCategory.SAFETY, "insufficient_risk_warning"),
                    category=ValidationCategory.SAFETY,
                    severity=ValidationSeverity.MEDIUM,
                    title="Недостаточные предупреждения о рисках",
                    description=f"Упоминаются риски ({', '.join(risk_mentions[:3])}), но недостаточно предупреждений",
                    suggestions=[
                        "Добавить явные предупреждения о возможных последствиях",
                        "Выделить риски в отдельный раздел",
                        "Использовать предупреждающие формулировки"
                    ]
                ))

        return issues

    def _check_dangerous_advice(self, response: StructuredResponse) -> List[ValidationIssue]:
        """Проверка опасных советов"""
        issues = []

        full_text = " ".join(response.sections.values())

        # Поиск опасных советов
        for dangerous_phrase in self.safety_keywords['dangerous_advice']:
            pattern = re.compile(r'\b' + re.escape(dangerous_phrase.lower()) + r'\b', re.IGNORECASE)
            matches = list(pattern.finditer(full_text.lower()))

            if matches:
                # Извлечение контекста
                contexts = []
                for match in matches:
                    start = max(0, match.start() - 50)
                    end = min(len(full_text), match.end() + 50)
                    contexts.append(full_text[start:end])

                issues.append(ValidationIssue(
                    issue_id=self._generate_issue_id(ValidationCategory.SAFETY, f"dangerous_advice_{len(issues)}"),
                    category=ValidationCategory.SAFETY,
                    severity=ValidationSeverity.CRITICAL,
                    title="Потенциально опасный совет",
                    description=f"Обнаружена рекомендация, которая может нарушать законодательство: '{dangerous_phrase}'",
                    text_fragment=contexts[0] if contexts else None,
                    suggestions=[
                        "Удалить или переформулировать потенциально опасный совет",
                        "Заменить на законную альтернативу",
                        "Добавить предупреждение о правовых последствиях"
                    ]
                ))

        return issues