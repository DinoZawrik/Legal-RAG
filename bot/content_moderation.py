"""Модуль модерации контента"""

import re
from typing import List, Tuple, Dict


class ContentModerator:
    """Класс для модерации контента"""

    def __init__(self):
        # Список запрещенных слов (пример)
        self.forbidden_words = {
            "спам",
            "реклама",
            "продам",
            "куплю",
            "заработок",
            # Добавить другие по необходимости
        }

        # Паттерны подозрительного контента
        self.suspicious_patterns = [
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",  # URLs
            r"\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b",  # Номера карт
            r"\b\d{10,}\b",  # Подозрительно длинные числа
        ]

    def check_content(self, text: str) -> Dict[str, any]:
        """Проверяет контент на нарушения"""
        issues = []
        severity = "low"

        # Проверка на запрещенные слова
        text_lower = text.lower()
        found_words = [word for word in self.forbidden_words if word in text_lower]
        if found_words:
            issues.append(f"Найдены запрещенные слова: {', '.join(found_words)}")
            severity = "medium"

        # Проверка на подозрительные паттерны
        for pattern in self.suspicious_patterns:
            if re.search(pattern, text):
                issues.append("Найден подозрительный контент")
                severity = "high"
                break

        # Проверка длины сообщения
        if len(text) > 4000:
            issues.append("Сообщение слишком длинное")

        # Проверка на повторяющиеся символы
        if re.search(r"(.)\1{10,}", text):
            issues.append("Обнаружен спам (повторяющиеся символы)")
            severity = "medium"

        return {
            "is_safe": len(issues) == 0,
            "issues": issues,
            "severity": severity,
            "action": self._recommend_action(severity),
        }

    def _recommend_action(self, severity: str) -> str:
        """Рекомендует действие на основе серьезности нарушения"""
        actions = {"low": "log", "medium": "warn", "high": "block"}
        return actions.get(severity, "log")

    def sanitize_text(self, text: str) -> str:
        """Очищает текст от потенциально опасного контента"""
        # Убираем URL
        text = re.sub(r"http[s]?://[^\s]+", "[ССЫЛКА_УДАЛЕНА]", text)

        # Убираем номера карт
        text = re.sub(r"\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b", "[НОМЕР_УДАЛЕН]", text)

        # Убираем email адреса
        text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_УДАЛЕН]", text)

        return text
