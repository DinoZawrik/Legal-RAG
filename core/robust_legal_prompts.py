#!/usr/bin/env python3
"""
УСТОЙЧИВЫЕ ПРАВОВЫЕ ПРОМПТЫ
Комбинирует лучшие техники для максимальной стабильности
- Fallback между JSON и обычными промптами
- Улучшенные инструкции цитирования
- Robust error handling
"""

def get_robust_legal_system_prompt():
    """Устойчивый системный промпт с четкими инструкциями"""
    return """Ты - эксперт по российскому законодательству, специализирующийся на концессионных соглашениях.

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА ОТВЕТА:

1. ФОРМАТ ОТВЕТА:
   - Начинай ВСЕГДА с точной ссылки: "Статья [номер] [название нормативного акта]"
   - Далее кратко объясни суть нормы
   - Используй ТОЛЬКО информацию из предоставленного контекста

2. ПРИМЕРЫ ПРАВИЛЬНЫХ ОТВЕТОВ:
   "Статья 10.1 профильного нормативного акта регулирует финансовое участие концедента в создании объекта концессионного соглашения."

   "Статья 5 часть 2 профильного нормативного акта устанавливает, что концессионер не вправе без согласия концедента передавать в залог свои права."

3. КРИТИЧЕСКИЕ ЗАПРЕТЫ:
   - НЕ начинай с общих фраз типа "В соответствии с законодательством"
   - НЕ придумывай статьи, которых нет в контексте
   - НЕ давай неточные или примерные ссылки

4. ЕСЛИ НЕТ ТОЧНОЙ ИНФОРМАЦИИ:
   - Прямо скажи: "В предоставленных документах точная информация не найдена"
   - НЕ пытайся отвечать приблизительно"""

def get_robust_legal_user_prompt_template():
    """Шаблон пользовательского промпта с улучшенным контекстом"""
    return """ДОКУМЕНТЫ ИЗ ПРАВОВОЙ БАЗЫ:
{context}

ВАЖНО: Используй только информацию из документов выше.

ВОПРОС: {query}

ОТВЕТ (начни с точной ссылки на статью):"""

def format_robust_context(chunks):
    """Форматирует контекст с максимальной ясностью для модели"""
    if not chunks:
        return "Документы не найдены."

    formatted_context = ""

    for i, chunk in enumerate(chunks, 1):
        text = chunk.get('text', '') if isinstance(chunk, dict) else str(chunk)
        metadata = chunk.get('metadata', {}) if isinstance(chunk, dict) else {}

        # Извлекаем метаданные
        law_number = metadata.get('law_number', 'Неизвестно')
        article = metadata.get('article', 'Неизвестно')
        chapter = metadata.get('chapter', '')

        # Очищаем от лишней информации
        if law_number != 'Неизвестно':
            law_number = law_number.replace('-FZ', '-ФЗ').replace('FZ', 'ФЗ')

        formatted_context += f"""
ДОКУМЕНТ {i}:
Источник: Федеральный закон {law_number}
Статья: {article}
{f"Глава: {chapter}" if chapter else ""}
Текст: {text.strip()}

"""

    return formatted_context.strip()

class RobustLegalPromptEngine:
    """Устойчивый движок правовых промптов с fallback стратегиями"""

    def __init__(self):
        self.system_prompt = get_robust_legal_system_prompt()
        self.user_template = get_robust_legal_user_prompt_template()

    def generate_robust_prompt(self, query: str, chunks: list) -> tuple:
        """Генерирует устойчивый промпт"""

        # Форматируем контекст
        formatted_context = format_robust_context(chunks)

        # Создаем промпт
        from core.prompt_sanitizer import sanitize_query, sanitize_context
        user_prompt = self.user_template.format(
            context=sanitize_context(formatted_context),
            query=sanitize_query(query)
        )

        return self.system_prompt, user_prompt

    def analyze_response_quality(self, response: str, query: str) -> dict:
        """Анализирует качество ответа"""
        if not response:
            return {'score': 0.0, 'issues': ['Empty response']}

        issues = []
        score = 1.0

        # Проверяем наличие ссылки на статью
        has_article_ref = any(phrase in response.lower() for phrase in [
            'статья', 'ст.', 'часть', 'пункт'
        ])

        if not has_article_ref:
            issues.append('No article reference')
            score -= 0.3

        # Проверяем наличие ссылки на закон
        has_law_ref = any(phrase in response.lower() for phrase in [
            '115-фз', '224-фз', 'федерального закона'
        ])

        if not has_law_ref:
            issues.append('No law reference')
            score -= 0.3

        # Проверяем на общие фразы
        generic_phrases = [
            'в соответствии с законодательством',
            'согласно нормам права',
            'как правило'
        ]

        if any(phrase in response.lower() for phrase in generic_phrases):
            issues.append('Contains generic phrases')
            score -= 0.2

        # Проверяем длину ответа
        if len(response) < 50:
            issues.append('Response too short')
            score -= 0.2
        elif len(response) > 2000:
            issues.append('Response too long')
            score -= 0.1

        return {
            'score': max(0.0, score),
            'issues': issues,
            'has_article_ref': has_article_ref,
            'has_law_ref': has_law_ref
        }

if __name__ == '__main__':
    # Тест устойчивого промпт-движка
    engine = RobustLegalPromptEngine()

    test_chunks = [
        {
            'text': 'Статья 10.1. Финансовое участие концедента в создании объекта концессионного соглашения',
            'metadata': {
                'law_number': '115-FZ',
                'article': '10.1',
                'chapter': 'Глава 2'
            }
        }
    ]

    system_prompt, user_prompt = engine.generate_robust_prompt(
        "Какая статья регулирует финансовое участие концедента?",
        test_chunks
    )

    print("=== ТЕСТ ROBUST LEGAL PROMPT ENGINE ===")
    print(f"System prompt length: {len(system_prompt)}")
    print(f"User prompt length: {len(user_prompt)}")

    # Тест анализа качества
    test_response = "Статья 10.1 Федерального закона 115-ФЗ регулирует финансовое участие концедента."
    quality = engine.analyze_response_quality(test_response, "test query")
    print(f"Quality score: {quality['score']:.2f}")
    print(f"Issues: {quality['issues']}")

    print(" Robust Legal Prompt Engine готов к использованию")