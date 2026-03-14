#!/usr/bin/env python3
"""
Text Normalization для юридических документов
Решает проблему переносов строк в терминах
"""
import re
import logging

logger = logging.getLogger(__name__)


def normalize_legal_text(text: str) -> str:
    """
    Нормализация юридического текста для улучшения поиска.

    Проблемы которые решаем:
    1. Переносы строк внутри терминов: "плата \nконцедента" "плата концедента"
    2. Дефисы с переносами: "плата - \nконцедента" "плата концедента"
    3. Множественные пробелы
    4. Лишние пробелы вокруг знаков препинания

    Args:
        text: Исходный текст из PDF

    Returns:
        Нормализованный текст
    """
    if not text:
        return text

    original_length = len(text)

    # 1. Убираем перенос строки после дефиса с пробелами: "плата - \nконцедента"
    # Паттерн: слово + пробелы + дефис + пробелы + перенос + пробелы + слово
    text = re.sub(r'(\w+)\s*-\s*\n\s*(\w)', r'\1 \2', text)

    # 2. Убираем перенос строки между частями многословного термина
    # Паттерн: слово (кириллица) + перенос + слово (кириллица) в нижнем регистре
    # Пример: "плата\nконцедента" "плата концедента"
    text = re.sub(r'([а-яё]+)\s*\n\s*([а-яё][а-яё]+)', r'\1 \2', text, flags=re.IGNORECASE)

    # 3. Убираем дефис в начале строки (остаток от переноса)
    # "плата \n- концедента" "плата концедента"
    text = re.sub(r'\n\s*-\s+(\w)', r' \1', text)

    # 4. Объединяем переносы слов с дефисом в конце строки
    # "пуб-\nличного" "публичного"
    text = re.sub(r'([а-яё]+)-\s*\n\s*([а-яё]+)', r'\1\2', text, flags=re.IGNORECASE)

    # 5. Заменяем множественные пробелы на один
    text = re.sub(r'[ \t]+', ' ', text)

    # 6. Убираем пробелы перед знаками препинания
    text = re.sub(r'\s+([,.;:!?)])', r'\1', text)

    # 7. Убираем пробелы после открывающих скобок
    text = re.sub(r'([\(])\s+', r'\1', text)

    # 8. Нормализуем множественные переносы строк
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 9. Убираем пробелы в начале и конце строк
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    normalized_length = len(text)
    logger.debug(f"Text normalized: {original_length} {normalized_length} chars")

    return text


def normalize_term_for_search(term: str) -> str:
    """
    Нормализация поискового термина.

    Args:
        term: Термин для поиска (например, "плата концедента")

    Returns:
        Нормализованный термин
    """
    # Приводим к нижнему регистру
    term = term.lower()

    # Убираем лишние пробелы
    term = re.sub(r'\s+', ' ', term)

    # Убираем пробелы в начале и конце
    term = term.strip()

    return term


def contains_term(text: str, term: str, case_sensitive: bool = False) -> bool:
    """
    Проверка содержит ли текст термин (с учетом нормализации).

    Args:
        text: Текст для поиска
        term: Термин для поиска
        case_sensitive: Учитывать регистр

    Returns:
        True если термин найден
    """
    # Нормализуем оба текста
    normalized_text = normalize_legal_text(text)
    normalized_term = normalize_term_for_search(term)

    if not case_sensitive:
        normalized_text = normalized_text.lower()
        normalized_term = normalized_term.lower()

    return normalized_term in normalized_text


def extract_context_around_term(text: str, term: str, context_chars: int = 100) -> str:
    """
    Извлечь контекст вокруг термина.

    Args:
        text: Текст
        term: Термин для поиска
        context_chars: Количество символов контекста

    Returns:
        Контекст вокруг термина или пустая строка
    """
    normalized_text = normalize_legal_text(text)
    normalized_term = normalize_term_for_search(term)

    text_lower = normalized_text.lower()
    term_lower = normalized_term.lower()

    pos = text_lower.find(term_lower)
    if pos == -1:
        return ""

    start = max(0, pos - context_chars)
    end = min(len(normalized_text), pos + len(normalized_term) + context_chars)

    context = normalized_text[start:end]

    # Добавляем многоточия если обрезали
    if start > 0:
        context = "..." + context
    if end < len(normalized_text):
        context = context + "..."

    return context


# Пример использования
if __name__ == "__main__":
    # Тестовый текст с проблемами
    test_text = """Статья 10.1. Уплачиваемая платой концедента

1. Уплачиваемая платой концедента может осуществляться в виде или совокупности по
следующим видам:
1) финансирования за счет средств в (или) имущественного взноса концедента
выплаты за создание и (или) имущественного взноса концедента
уплачиваемой (далее - плата
концедента). В случае, финансирования"""

    print("Оригинальный текст:")
    print(test_text)
    print("\n" + "="*80 + "\n")

    normalized = normalize_legal_text(test_text)
    print("Нормализованный текст:")
    print(normalized)
    print("\n" + "="*80 + "\n")

    # Проверка поиска
    term = "плата концедента"
    found = contains_term(test_text, term)
    print(f"Термин '{term}' найден: {found}")

    if found:
        context = extract_context_around_term(test_text, term, 50)
        print(f"Контекст: {context}")
