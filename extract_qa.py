#!/usr/bin/env python3
"""
Извлекает только вопросы и ответы из JSON результатов теста
"""
import json

# Читаем JSON
with open('test_40_natural_answers_20251005_222816.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Создаем txt файл
with open('test_40_questions_and_answers.txt', 'w', encoding='utf-8') as f:
    f.write("РЕЗУЛЬТАТЫ ТЕСТА: 40 ВОПРОСОВ С ЕСТЕСТВЕННЫМИ ОТВЕТАМИ\n")
    f.write("="*80 + "\n\n")
    
    for result in data['results']:
        if result.get('success'):
            f.write(f"Вопрос {result['question_number']}/40\n\n")
            f.write(f"{result['question']}\n\n")
            f.write(f"{result['answer']}\n\n")
            f.write("="*80 + "\n\n")
        else:
            # Для неудачных вопросов тоже добавим
            f.write(f"Вопрос {result['question_number']}/40 (ОШИБКА)\n\n")
            f.write(f"{result['question']}\n\n")
            f.write(f"[Ответ не получен: {result.get('error', 'Unknown error')}]\n\n")
            f.write("="*80 + "\n\n")

print("Сохранено в test_40_questions_and_answers.txt")
print(f"Всего вопросов: {len(data['results'])}")
print(f"Успешных ответов: {data['test_info']['success_count']}")
