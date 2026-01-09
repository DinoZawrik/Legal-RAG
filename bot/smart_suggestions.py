"""Модуль интеллектуальных предложений"""

import re
from typing import List, Set
from collections import Counter


class SmartSuggestions:
    """Класс для генерации умных предложений"""

    def __init__(self):
        # Ключевые слова для разных категорий
        self.finance_keywords = {
            "млн",
            "руб",
            "бюджет",
            "финансирование",
            "стоимость",
            "сумма",
            "инвестиции",
            "затраты",
            "расходы",
            "доходы",
        }

        self.project_keywords = {
            "проект",
            "соглашение",
            "создание",
            "эксплуатация",
            "завершение",
            "строительство",
            "развитие",
            "модернизация",
        }

        self.region_keywords = {
            "федеральный",
            "региональный",
            "муниципальный",
            "область",
            "край",
            "республика",
            "округ",
            "город",
        }

    def suggest_questions(self, user_input: str, document_context: List[str]) -> List[str]:
        """Предлагает вопросы на основе ввода пользователя"""
        suggestions = []
        input_lower = user_input.lower()

        # Анализируем намерения пользователя
        if self._contains_keywords(input_lower, self.finance_keywords):
            suggestions.extend(
                [
                    "Какая общая сумма финансирования по всем проектам?",
                    "Сравни бюджеты федерального и регионального уровней",
                    "Какие проекты имеют самое большое финансирование?",
                ]
            )

        if self._contains_keywords(input_lower, self.project_keywords):
            suggestions.extend(
                [
                    "Сколько проектов находится на стадии создания?",
                    "Какие проекты уже завершены?",
                    "Покажи статистику по стадиям реализации",
                ]
            )

        if self._contains_keywords(input_lower, self.region_keywords):
            suggestions.extend(
                [
                    "Сравни активность регионов по количеству проектов",
                    "Какой уровень власти реализует больше проектов?",
                    "Покажи региональную статистику",
                ]
            )

        # Если нет специфичных ключевых слов, предлагаем общие вопросы
        if not suggestions:
            suggestions = [
                "Расскажи о ключевых показателях в документах",
                "Какая основная тематика документов?",
                "Покажи самые важные данные",
            ]

        return suggestions[:5]  # Ограничиваем количество предложений

    def _contains_keywords(self, text: str, keywords: Set[str]) -> bool:
        """Проверяет наличие ключевых слов в тексте"""
        return any(keyword in text for keyword in keywords)

    def extract_entities(self, text: str) -> dict:
        """Извлекает сущности из текста"""
        entities = {
            "numbers": re.findall(r"\d+(?:\s+\d+)*", text),
            "regions": [],
            "amounts": re.findall(r"\d+(?:\s+\d+)*\s*(?:млн|тыс)\.?\s*руб\.?", text),
        }

        # Можно добавить более сложную обработку NER
        return entities
