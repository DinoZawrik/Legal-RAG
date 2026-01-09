"""Инициализация базовых промптов."""

from __future__ import annotations

from typing import Dict

from .snippets import (
    base_system_prompt,
    comparison_additions,
    definition_additions,
    legal_additions,
    procedure_additions,
    regulatory_additions,
)
from .types import ModelType, PromptTemplate, QueryType


def initialize_templates(model_type: ModelType) -> Dict[str, PromptTemplate]:
    base_system = base_system_prompt()

    templates: Dict[str, PromptTemplate] = {}

    templates["casual_chat"] = PromptTemplate(
        name="casual_chat",
        query_type=QueryType.CASUAL_CHAT,
        model_type=model_type,
        system_prompt="""
Ты - дружелюбный AI-помощник. Отвечай естественно и просто на обычные вопросы.

ПРАВИЛА ДЛЯ ОБЫЧНОГО ОБЩЕНИЯ:
• Будь дружелюбным и естественным
• Отвечай кратко и по существу
• НЕ требуй никаких документов
• НЕ используй формальный юридический язык
• Используй свои общие знания
• Если не знаешь - честно скажи об этом
            """,
        user_prompt_template="{query}",
        description="Для обычного общения и простых вопросов",
    )

    templates["simple_definition"] = PromptTemplate(
        name="simple_definition",
        query_type=QueryType.SIMPLE_DEFINITION,
        model_type=model_type,
        system_prompt=base_system + definition_additions(),
        user_prompt_template="""
Вопрос: {query}

Контекст из документов:
{chunks}

🔥 КРИТИЧЕСКИ ВАЖНО: Если вопрос содержит слова "сколько", "количество", "объем", "число" - ты ОБЯЗАН найти ТОЧНЫЕ числа в документах выше и привести их БЕЗ изменений. 
НЕ давай общие ответы типа "несколько тысяч" или "около 4000-5000"!
Ищи в документах такие числа как "3 411", "4 616", "2172", "1239" и т.д. и ОБЯЗАТЕЛЬНО приводи их!

Дай четкое и понятное определение, структурируй ответ логично.""",
        description="Для простых вопросов-определений",
    )

    templates["complex_procedure"] = PromptTemplate(
        name="complex_procedure",
        query_type=QueryType.COMPLEX_PROCEDURE,
        model_type=model_type,
        system_prompt=base_system + procedure_additions(),
        user_prompt_template="""
Вопрос о процедуре: {query}

Контекст из нормативных документов:
{chunks}

Опиши пошаговую процедуру, укажи все этапы и требования.""",
        description="Для вопросов о процедурах и порядках",
    )

    templates["comparison"] = PromptTemplate(
        name="comparison",
        query_type=QueryType.COMPARISON,
        model_type=model_type,
        system_prompt=base_system + comparison_additions(),
        user_prompt_template="""
Вопрос для сравнения: {query}

Информация для анализа:
{chunks}

Проведи детальное сравнение, выдели ключевые различия и сходства.""",
        description="Для сравнительных вопросов",
    )

    templates["legal_analysis"] = PromptTemplate(
        name="legal_analysis",
        query_type=QueryType.LEGAL_ANALYSIS,
        model_type=model_type,
        system_prompt=base_system + legal_additions(),
        user_prompt_template="""
Правовой вопрос: {query}

Нормативная база:
{chunks}

Проведи глубокий правовой анализ с учетом иерархии нормативных актов.""",
        description="Для глубокого правового анализа",
    )

    templates["regulatory_specific"] = PromptTemplate(
        name="regulatory_specific",
        query_type=QueryType.REGULATORY_SPECIFIC,
        model_type=model_type,
        system_prompt=base_system + regulatory_additions(),
        user_prompt_template="""
Вопрос по нормативу: {query}

Выдержки из технических документов:
{chunks}

Дай точный ответ со ссылкой на конкретные технические требования.""",
        description="Для вопросов по СП, ГОСТ, СанПиН",
    )

    return templates


__all__ = ["initialize_templates"]
