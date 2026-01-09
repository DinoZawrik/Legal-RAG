"""Prompt builders for regulatory pipeline."""

from langchain_core.prompts import ChatPromptTemplate


def build_extraction_prompt() -> ChatPromptTemplate:
    system_message = """
    Вы - эксперт по анализу регулятивных документов. 
    Извлеките ключевую информацию из предоставленного текста документа.
    Извлеките следующую информацию:
    1. Тип документа (закон, постановление, приказ, etc.)
    2. Номер документа
    3. Дата принятия
    4. Орган, принявший документ
    5. Краткое содержание (2-3 предложения)
    6. Ключевые требования или положения
    7. Сфера применения
    8. Связанные документы (если упоминаются)
    Предоставьте результат в JSON формате.
    """
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "Документ для анализа:\n\n{document_text}"),
    ])


def build_validation_prompt() -> ChatPromptTemplate:
    system_message = """
    Проверьте корректность извлеченной информации из регулятивного документа.
    Убедитесь, что:
    1. Формат данных соответствует ожиданиям
    2. Даты имеют правильный формат
    3. Номера документов корректны
    4. Нет очевидных ошибок в извлечении
    Предоставьте валидированный JSON или укажите на ошибки.
    """
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "Проверьте данные:\n\n{extracted_data}"),
    ])


def build_presentation_extraction_prompt() -> ChatPromptTemplate:
    system_message = """
    Вы - эксперт по анализу презентаций. Вам нужно извлечь структурированную
    информацию из презентации (формат PDF/PowerPoint).

    Для каждой страницы извлеките:
    - Заголовок (если есть)
    - Основные ключевые пункты (bullet points)
    - Цифровые показатели и метрики
    - Визуальные элементы (диаграммы, графики) с описанием
    - Выводы или рекомендации

    Возвращайте результат в формате JSON со следующей структурой:
    {
      "page_number": int,
      "title": str,
      "key_points": List[str],
      "metrics": List[str],
      "visuals": List[str],
      "insights": List[str]
    }
    """
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "Страница {page_number} презентации:\n\n{page_text}"),
    ])


def build_presentation_page_scanning_prompt() -> ChatPromptTemplate:
    system_message = """
    Вы - эксперт по анализу презентаций. Вам нужно детально проанализировать
    страницу презентации и выделить ключевую информацию.

    Структура ответа:
    {
      "page_number": int,
      "topics": [
        {
          "title": str,
          "description": str,
          "evidence": List[str],
          "metrics": List[str],
          "actions": List[str]
        }
      ],
      "summary": str,
      "questions": List[str],
      "confidence": float
    }

    Обеспечьте, чтобы каждый вопрос был осмысленным и основанным на содержании страницы.
    """
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "Анализ страницы {page_number}:\n\n{page_text}"),
    ])


def build_presentation_quality_check_prompt() -> ChatPromptTemplate:
    system_message = """
    Вы - эксперт по контролю качества анализа презентаций. Проверьте результаты
    извлечения информации со страницы презентации.

    Требуемая структура JSON ответа:
    {
      "quality_score": str,  # например "HIGH", "MEDIUM", "LOW"
      "retry_needed": bool,
      "issues": List[str],
      "suggestions": str,
      "verdict": "accept" | "retry"
    }

    Проверьте:
    - Полноту обязательных полей (topics, summary, metrics)
    - Логическую связность текста
    - Корректность числовых значений
    - Релевантность вопросов
    - Обоснованность confidence
    """
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "Проверьте результат:\n\n{page_result}"),
    ])


def build_presentation_retry_prompt() -> ChatPromptTemplate:
    system_message = """
    Проанализируйте страницу презентации повторно, учитывая замечания из проверки качества.
    Исправьте указанные проблемы, особенно в полях key_points, metrics и visuals.
    Обновите summary и questions в соответствии с новыми данными.

    Сохраните ту же структуру JSON, что и при первичном сканировании страницы.
    """
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        (
            "human",
            "Страница {page_number} презентации (повторный анализ):\n\n"
            "Исходный текст:\n{page_text}\n\nЗамечания: {feedback}",
        ),
    ])


def build_presentation_aggregation_prompt() -> ChatPromptTemplate:
    system_message = """
    Вы - эксперт по аналитике презентаций. Нужно агрегировать результаты обработки
    всех страниц презентации.

    Сформируйте итоговый отчет со следующей структурой:
    {
      "overview": str,
      "key_findings": List[str],
      "strategic_insights": List[str],
      "risk_factors": List[str],
      "recommended_actions": List[str],
      "appendix": {
         "page_summaries": List[{
            "page_number": int,
            "summary": str,
            "highlights": List[str]
         }]
      }
    }
    """
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "Результаты страниц для агрегирования:\n\n{page_results}"),
    ])


__all__ = [
    "build_extraction_prompt",
    "build_validation_prompt",
    "build_presentation_extraction_prompt",
    "build_presentation_page_scanning_prompt",
    "build_presentation_quality_check_prompt",
    "build_presentation_retry_prompt",
    "build_presentation_aggregation_prompt",
]
