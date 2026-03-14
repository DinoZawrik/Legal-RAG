#!/usr/bin/env python3
"""
ПРОДВИНУТЫЕ СТРУКТУРИРОВАННЫЕ ПРОМПТЫ по рекомендациям Gemini
- JSON структурированный вывод
- Chain-of-Thought рассуждения
- Строгое форматирование цитат
"""

def get_structured_legal_system_prompt():
    """Системный промпт для структурированного JSON вывода"""
    return """Ты - высокоточный юридический ассистент-аналитик российского законодательства.

КРИТИЧЕСКИ ВАЖНО: Твой ответ ОБЯЗАТЕЛЬНО должен быть в формате JSON.

JSON должен содержать три ключа: "reasoning", "answer" и "citations".

СТРУКТУРА ОТВЕТА:
{
  "reasoning": "Здесь пропиши свой план рассуждений: 1) какую правовую норму ищет пользователь, 2) какие фрагменты из контекста отвечают на вопрос, 3) как ты синтезируешь ответ",
  "answer": "Четкий прямой ответ на вопрос пользователя",
  "citations": [
    {
      "law": "115-ФЗ",
      "article": "10.1",
      "part": "1",
      "point": null,
      "text": "Точная цитата из предоставленного контекста"
    }
  ]
}

ПРАВИЛА ЗАПОЛНЕНИЯ:
- "reasoning": Обязательная цепочка рассуждений в 2-3 предложения
- "answer": Начинай с точной ссылки на статью и закон, потом краткое объяснение
- "citations": Массив ВСЕХ использованных источников с точными метаданными

СТРОЖАЙШИЕ ЗАПРЕТЫ:
- НЕ придумывай информацию, которой нет в контексте
- НЕ ссылайся на статьи, которых нет среди предоставленных фрагментов
- НЕ возвращай ответ НЕ в JSON формате
- НЕ используй общие фразы без конкретных ссылок

ОБЯЗАТЕЛЬНО: Каждая часть ответа должна быть подкреплена цитатой из citations."""

def get_structured_legal_user_prompt_template():
    """Шаблон пользовательского промпта для структурированного вывода"""
    return """КОНТЕКСТ ИЗ ПРАВОВЫХ ДОКУМЕНТОВ:
{context}

ПРИМЕР ПРАВИЛЬНОГО JSON ОТВЕТА:

Вопрос: "Какая статья регулирует финансовое участие концедента?"
JSON ответ:
{{
  "reasoning": "Пользователь ищет правовую норму о финансовом участии концедента. В предоставленных фрагментах есть статья 10.1 из 115-ФЗ, которая напрямую регулирует этот вопрос. Формулирую ответ на основе этого фрагмента.",
  "answer": "Статья 10.1 Федерального закона 115-ФЗ регулирует финансовое участие концедента в создании объекта концессионного соглашения.",
  "citations": [
    {{
      "law": "115-ФЗ",
      "article": "10.1",
      "part": null,
      "point": null,
      "text": "Статья 10.1. Финансовое участие концедента в создании объекта концессионного соглашения"
    }}
  ]
}}

АНАЛИЗИРУЕМЫЙ ВОПРОС: {query}

Выполни внутренний анализ:
1. Анализ вопроса: Какую правовую норму ищет пользователь?
2. Поиск в контексте: Какие фрагменты отвечают на вопрос?
3. Синтез: Как объединить информацию из найденных фрагментов?
4. Проверка: Все ли части ответа подкреплены цитатами?

ТВОЙ JSON ОТВЕТ:"""

def get_enhanced_context_formatter_structured(chunks):
    """Форматирует чанки с детальными метаданными для структурированного анализа"""
    formatted_context = ""

    for i, chunk in enumerate(chunks, 1):
        text = chunk.get('text', '') if isinstance(chunk, dict) else str(chunk)
        metadata = chunk.get('metadata', {}) if isinstance(chunk, dict) else {}

        # Извлекаем все доступные метаданные
        law_number = metadata.get('law_number', 'Неизвестно')
        article = metadata.get('article', 'Неизвестно')
        chapter = metadata.get('chapter', '')
        part = metadata.get('part', '')
        point = metadata.get('point', '')

        formatted_context += f"""
===== ФРАГМЕНТ {i} =====
МЕТАДАННЫЕ:
- Закон: {law_number}
- Статья: {article}
- Глава: {chapter}
- Часть: {part}
- Пункт: {point}

ТЕКСТ:
{text}

"""

    return formatted_context.strip()

class AdvancedStructuredPromptEngine:
    """Движок продвинутых структурированных промптов по рекомендациям Gemini"""

    def __init__(self):
        self.system_prompt = get_structured_legal_system_prompt()
        self.user_template = get_structured_legal_user_prompt_template()

    def generate_structured_prompt(self, query: str, chunks: list) -> tuple:
        """Генерирует структурированный промпт для JSON вывода"""

        # Форматируем контекст с детальными метаданными
        formatted_context = get_enhanced_context_formatter_structured(chunks)

        # Создаем пользовательский промпт
        from core.prompt_sanitizer import sanitize_query, sanitize_context
        user_prompt = self.user_template.format(
            context=sanitize_context(formatted_context),
            query=sanitize_query(query)
        )

        return self.system_prompt, user_prompt

    def validate_json_response(self, response: str) -> dict:
        """Проверяет и парсит JSON ответ"""
        import json

        try:
            # Пытаемся парсить JSON
            parsed = json.loads(response)

            # Проверяем обязательные поля
            required_fields = ['reasoning', 'answer', 'citations']
            for field in required_fields:
                if field not in parsed:
                    return {'valid': False, 'error': f'Missing required field: {field}'}

            # Проверяем citations
            if not isinstance(parsed['citations'], list):
                return {'valid': False, 'error': 'Citations must be a list'}

            for citation in parsed['citations']:
                if not isinstance(citation, dict):
                    return {'valid': False, 'error': 'Each citation must be an object'}

                citation_fields = ['law', 'article', 'text']
                for field in citation_fields:
                    if field not in citation:
                        return {'valid': False, 'error': f'Missing citation field: {field}'}

            return {'valid': True, 'data': parsed}

        except json.JSONDecodeError as e:
            return {'valid': False, 'error': f'Invalid JSON: {e}'}

if __name__ == '__main__':
    # Тест структурированного промпт-движка
    engine = AdvancedStructuredPromptEngine()

    test_chunks = [
        {
            'text': 'Статья 10.1. Финансовое участие концедента в создании объекта концессионного соглашения',
            'metadata': {
                'law_number': '115-ФЗ',
                'article': '10.1',
                'chapter': 'Глава 2',
                'part': '1',
                'point': ''
            }
        }
    ]

    system_prompt, user_prompt = engine.generate_structured_prompt(
        "Какая статья регулирует финансовое участие концедента?",
        test_chunks
    )

    print("=== ТЕСТ ADVANCED STRUCTURED PROMPT ENGINE ===")
    print(f"System prompt length: {len(system_prompt)}")
    print(f"User prompt length: {len(user_prompt)}")
    print(" Advanced Structured Prompt Engine готов к использованию")