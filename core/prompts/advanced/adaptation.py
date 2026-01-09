"""Адаптация промптов под контекст."""

from __future__ import annotations

from typing import List, Optional

from .types import PromptContext


def adapt_system_prompt(
    base_prompt: str,
    chunks: List[str],
    context: Optional[PromptContext],
    config: dict,
) -> str:
    if not config.get("enable_context_adaptation", True):
        return base_prompt

    adaptations: List[str] = []

    chunks_count = len(chunks)
    if chunks_count < config.get("min_chunks_for_detailed", 3):
        adaptations.append(
            """

ОСОБЫЕ ИНСТРУКЦИИ (мало данных):
• Используй логические выводы и косвенные данные
• Анализируй общие принципы регулирования
• Делай обоснованные предположения на основе имеющихся норм
• Предупреждай о необходимости дополнительной проверки"""
        )
    elif chunks_count > config.get("max_chunks_for_summary", 10):
        adaptations.append(
            """

ОСОБЫЕ ИНСТРУКЦИИ (много данных):
• Фокусируйся на наиболее релевантной информации
• Структурируй ответ с четкой иерархией важности
• Выдели главные выводы в начале каждого раздела
• Избегай избыточной детализации"""
        )

    if context and context.document_types:
        doc_types = set(context.document_types)

        if {"закон", "постановление"} & doc_types:
            adaptations.append(
                """

КОНТЕКСТ: В ответе использована информация из высокоуровневых правовых актов.
• Подчеркивай обязательность требований
• Указывай на правовые последствия нарушений
• Акцентируй внимание на принципиальных положениях"""
            )

        if any(t in doc_types for t in ["сп", "гост", "снип"]):
            adaptations.append(
                """

КОНТЕКСТ: В ответе использованы технические нормативы.
• Фокусируйся на конкретных технических требованиях
• Указывай численные параметры и допуски
• Разъясняй методики применения норм"""
            )

    return base_prompt + "".join(adaptations)


def format_chunks_for_prompt(chunks: List[str]) -> str:
    if not chunks:
        return "Релевантные документы не найдены."

    formatted_chunks = []
    for i, chunk in enumerate(chunks, 1):
        if len(chunk) > 1500:
            chunk = chunk[:1500] + "..."
        formatted_chunks.append(f"Документ {i}:\n{chunk}")

    return "\n\n".join(formatted_chunks)


def adapt_user_prompt(
    template: str,
    query: str,
    chunks: List[str],
    context: Optional[PromptContext],
) -> str:
    chunks_text = format_chunks_for_prompt(chunks)
    adapted_prompt = template.format(query=query, chunks=chunks_text)

    if context:
        if context.has_exact_match:
            adapted_prompt += (
                "\n\n💡 Найдено точное совпадение в документах - используй эту информацию как основу ответа."
            )
        if context.confidence_level < 0.5:
            adapted_prompt += "\n\n⚠️ Уровень уверенности в найденных данных низкий - делай больше логических выводов."

    return adapted_prompt


__all__ = ["adapt_system_prompt", "adapt_user_prompt", "format_chunks_for_prompt"]
