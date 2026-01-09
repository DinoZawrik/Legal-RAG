"""Определение типа пользовательского запроса."""

from __future__ import annotations

from .types import QueryType


def detect_query_type(query: str) -> QueryType:
    query_lower = query.lower()

    casual_markers = [
        "привет",
        "здравствуй",
        "как дела",
        "как поживаешь",
        "что нового",
        "спасибо",
        "благодарю",
        "пока",
        "до свидания",
        "хорошо",
        "отлично",
        "кто ты",
        "как тебя зовут",
        "что ты умеешь",
        "расскажи о себе",
        "помоги",
        "можешь",
        "умеешь ли",
        "способен ли",
    ]

    if any(marker in query_lower for marker in casual_markers):
        return QueryType.CASUAL_CHAT

    legal_terms = [
        "закон",
        "статья",
        "норма",
        "требование",
        "регулирование",
        "право",
        "документ",
        "акт",
        "постановление",
        "приказ",
        "гост",
        "снип",
        "сп",
        "ценообразование",
        "тариф",
        "теплоснабжение",
        "теплоэнергия",
        "тепловая",
        "регуляторный",
        "основы",
        "принципы",
        "методика",
        "расчет",
        "норматив",
        "стандарт",
        "технический",
        "энергетический",
        "коммунальный",
        "жилищный",
        "правила",
        "порядок",
        "схема",
        "план",
        "программа",
        "система",
    ]

    is_short = len(query.split()) <= 3
    has_legal_term = any(term in query_lower for term in legal_terms)

    if is_short and not has_legal_term:
        return QueryType.CASUAL_CHAT

    numeric_markers = [
        "сколько",
        "какой объем",
        "какой размер",
        "количество",
        "число",
        "численность",
        "объём",
        "размер",
        "общий объем",
        "всего",
        "итого",
        "млрд",
        "миллиард",
        "тысяч",
        "млн",
        "миллион",
        "рублей",
        "соглашений",
        "договоров",
        "проектов",
    ]

    if any(marker in query_lower for marker in numeric_markers):
        return QueryType.SIMPLE_DEFINITION

    if any(phrase in query_lower for phrase in ["что такое", "определение", "понятие", "это", "означает"]):
        return QueryType.SIMPLE_DEFINITION

    if any(
        phrase in query_lower
        for phrase in ["как получить", "порядок", "процедура", "как оформить", "этапы", "последовательность", "алгоритм"]
    ):
        return QueryType.COMPLEX_PROCEDURE

    if any(
        phrase in query_lower
        for phrase in ["сравни", "различия", "отличия", "разница между", "общего", "чем отличается", "vs", "или"]
    ):
        return QueryType.COMPARISON

    if any(
        phrase in query_lower
        for phrase in ["сп ", "гост", "снип", "санпин", "требования к", "нормы", "параметры", "расчет", "норматив"]
    ):
        return QueryType.REGULATORY_SPECIFIC

    if any(
        phrase in query_lower
        for phrase in ["статья", "закон", "правовое", "юридический", "ответственность", "права", "обязанности"]
    ):
        return QueryType.LEGAL_ANALYSIS

    if has_legal_term:
        return QueryType.SIMPLE_DEFINITION

    return QueryType.CASUAL_CHAT


__all__ = ["detect_query_type"]
