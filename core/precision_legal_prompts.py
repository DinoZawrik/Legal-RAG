#!/usr/bin/env python3
"""
СВЕРХТОЧНЫЕ ПРАВОВЫЕ ПРОМПТЫ для повышения фактической корректности
Основано на рекомендациях Gemini и диагностике проблем
"""

def get_precision_legal_system_prompt():
    """Суперточный системный промпт для правовых вопросов"""
    return """Ты - высокоточный юридический ассистент-аналитик российского законодательства.

КРИТИЧЕСКИ ВАЖНЫЕ ИНСТРУКЦИИ - ВЫПОЛНЯЙ СТРОГО:

1. ФОРМАТ ОТВЕТА:
   - ВСЕГДА начинай ответ с точной ссылки на статью и закон
   - Формат: "Статья [номер] Федерального закона [номер]-ФЗ [название]"
   - Пример: "Статья 10.1 Федерального закона 115-ФЗ регулирует финансовое участие концедента"

2. РАБОТА С КОНТЕКСТОМ:
   - Используй ТОЛЬКО информацию из предоставленного контекста
   - НЕ добавляй информацию от себя
   - Если в контексте указаны метаданные "Источник: 115-FZ, Статья: 10.1" - ОБЯЗАТЕЛЬНО используй их

3. СТРУКТУРА ОТВЕТА:
   - Строка 1: Точная ссылка на статью
   - Строка 2-3: Краткое описание содержания статьи
   - При необходимости: дополнительная релевантная информация

4. ЗАПРЕЩАЕТСЯ:
   - Давать общие рассуждения без ссылок на статьи
   - Начинать с фраз типа "Финансовое участие является..."
   - Игнорировать метаданные о статьях и законах

5. ОБЯЗАТЕЛЬНО:
   - Указывать номер статьи, если он есть в контексте
   - Указывать номер закона (115-ФЗ, 224-ФЗ и т.д.)
   - Быть максимально конкретным и точным"""

def get_precision_legal_user_prompt_template():
    """Шаблон пользовательского промпта с примерами"""
    return """КОНТЕКСТ ИЗ ПРАВОВЫХ ДОКУМЕНТОВ:
{context}

ПРИМЕРЫ ПРАВИЛЬНЫХ ОТВЕТОВ:

Вопрос: "Какая статья регулирует финансовое участие концедента?"
Правильный ответ: "Статья 10.1 Федерального закона 115-ФЗ регулирует финансовое участие концедента в создании объекта концессионного соглашения."

Вопрос: "Можно ли изменять назначение объекта концессионного соглашения?"
Правильный ответ: "Статья 3 часть 5 Федерального закона 115-ФЗ устанавливает, что изменение назначения объекта концессионного соглашения не допускается."

ТВОЯ ЗАДАЧА:
Ответь на следующий вопрос, следуя примерам выше и используя ТОЛЬКО предоставленный контекст:

ВОПРОС: {query}

ОТВЕТ:"""

def get_enhanced_context_formatter(chunks):
    """Форматирует чанки с явными метаданными для модели"""
    formatted_context = ""

    for i, chunk in enumerate(chunks, 1):
        # Извлекаем данные из чанка
        text = chunk.get('text', '') if isinstance(chunk, dict) else str(chunk)
        metadata = chunk.get('metadata', {}) if isinstance(chunk, dict) else {}

        # Форматируем с явными метаданными
        law_number = metadata.get('law_number', 'Неизвестно')
        article = metadata.get('article', 'Неизвестно')

        formatted_context += f"""
ДОКУМЕНТ {i}:
Источник: Федеральный закон {law_number}
Статья: {article}
Содержание: {text}

"""

    return formatted_context.strip()

class PrecisionLegalPromptEngine:
    """Движок сверхточных правовых промптов"""

    def __init__(self):
        self.system_prompt = get_precision_legal_system_prompt()
        self.user_template = get_precision_legal_user_prompt_template()

    def generate_precision_prompt(self, query: str, chunks: list) -> tuple:
        """Генерирует сверхточный промпт для правовых вопросов"""

        # Форматируем контекст с метаданными
        formatted_context = get_enhanced_context_formatter(chunks)

        # Создаем пользовательский промпт
        from core.prompt_sanitizer import sanitize_query, sanitize_context
        user_prompt = self.user_template.format(
            context=sanitize_context(formatted_context),
            query=sanitize_query(query)
        )

        return self.system_prompt, user_prompt

    def test_prompt_quality(self, query: str, chunks: list) -> dict:
        """Тестирует качество промпта"""
        system_prompt, user_prompt = self.generate_precision_prompt(query, chunks)

        return {
            'system_prompt_length': len(system_prompt),
            'user_prompt_length': len(user_prompt),
            'chunks_count': len(chunks),
            'has_examples': 'Примеры правильных ответов:' in user_prompt,
            'has_strict_instructions': 'КРИТИЧЕСКИ ВАЖНЫЕ ИНСТРУКЦИИ' in system_prompt,
            'has_metadata_formatting': 'Источник:' in user_prompt
        }

if __name__ == '__main__':
    # Тест промпт-движка
    engine = PrecisionLegalPromptEngine()

    test_chunks = [
        {
            'text': 'Статья 10.1. Финансовое участие концедента в создании объекта концессионного соглашения',
            'metadata': {'law_number': '115-FZ', 'article': '10.1'}
        }
    ]

    system_prompt, user_prompt = engine.generate_precision_prompt(
        "Какая статья регулирует финансовое участие концедента?",
        test_chunks
    )

    print("=== ТЕСТ PRECISION PROMPT ENGINE ===")
    print(f"System prompt length: {len(system_prompt)}")
    print(f"User prompt length: {len(user_prompt)}")

    quality = engine.test_prompt_quality(
        "Какая статья регулирует финансовое участие концедента?",
        test_chunks
    )
    print(f"Quality metrics: {quality}")
    print(" Precision Legal Prompt Engine готов к использованию")