#!/usr/bin/env python3
"""
Валидация корректности индексации правовых данных
"""

import asyncio
import os
import sys

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.search_service import SearchService

async def validate_critical_legal_data():
    """Валидация критически важных правовых данных"""
    print('[VALIDATION] Testing critical legal data indexing...')
    print('=' * 60)

    try:
        # Инициализация
        search_service = SearchService()
        await search_service.initialize()

        if not search_service.storage_manager:
            print('[ERROR] Storage manager not available')
            return False

        # Критические поисковые запросы с ожидаемыми данными
        critical_tests = [
            {
                "query": "статья 10.1",
                "expected_content": ["финансовое участие", "концедент", "80", "восемьдесят процентов"],
                "description": "Article 10.1 - Financial participation"
            },
            {
                "query": "статья 3 часть 5",
                "expected_content": ["не допускается", "изменение", "назначение", "целевое"],
                "description": "Article 3.5 - Prohibition of purpose change"
            },
            {
                "query": "статья 5 часть 2",
                "expected_content": ["не вправе", "передавать", "залог", "концессионер"],
                "description": "Article 5.2 - Pledge prohibition"
            },
            {
                "query": "80 процентов",
                "expected_content": ["капитальный грант", "не может превышать", "финансовое участие"],
                "description": "80% financial limit"
            },
            {
                "query": "восемьдесят процентов",
                "expected_content": ["капитальный грант", "предельный размер"],
                "description": "Eighty percent limit (text form)"
            },
            {
                "query": "плата концедента",
                "expected_content": ["концедент", "концессионер", "статья 10"],
                "description": "Concedent payment definition"
            }
        ]

        passed_tests = 0
        total_tests = len(critical_tests)

        for i, test in enumerate(critical_tests, 1):
            print(f'\n[TEST {i}/{total_tests}] {test["description"]}')
            print(f'Query: "{test["query"]}"')
            print('-' * 40)

            try:
                # Поиск в базе данных
                results = await search_service.storage_manager.search_documents(
                    query=test["query"],
                    limit=5
                )

                if not results:
                    print('[FAIL] No results found')
                    continue

                print(f'[INFO] Found {len(results)} results')

                # Анализ содержимого
                found_content = []
                all_text = ""

                for j, result in enumerate(results):
                    text = result.get('text', '').lower()
                    all_text += " " + text
                    metadata = result.get('metadata', {})

                    print(f'  Result {j+1}: {metadata.get("law_number", "Unknown")} | Score: {result.get("similarity", 0.0):.3f}')
                    text_preview = text[:150] + "..." if len(text) > 150 else text
                    print(f'    Text: {text_preview}')

                # Проверка ожидаемого содержимого
                expected_found = 0
                for expected in test["expected_content"]:
                    if expected.lower() in all_text:
                        found_content.append(expected)
                        expected_found += 1

                # Оценка результата
                coverage = expected_found / len(test["expected_content"]) if test["expected_content"] else 0

                if coverage >= 0.5:  # 50%+ покрытие считается успехом
                    passed_tests += 1
                    status = "[PASS]"
                else:
                    status = "[FAIL]"

                print(f'{status} Coverage: {coverage:.1%} ({expected_found}/{len(test["expected_content"])})')
                print(f'Found content: {", ".join(found_content) if found_content else "None"}')

            except Exception as e:
                print(f'[ERROR] Test failed with exception: {e}')

        # Финальные результаты
        print('\n' + '=' * 60)
        print('[VALIDATION RESULTS]')
        print(f'Passed: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)')

        if passed_tests == total_tests:
            print('[EXCELLENT] All critical data properly indexed!')
        elif passed_tests >= total_tests * 0.8:
            print('[GOOD] Most critical data available')
        elif passed_tests >= total_tests * 0.5:
            print('[MODERATE] Some critical data missing')
        else:
            print('[POOR] Major issues with data indexing')

        # Дополнительная статистика
        print('\n[ADDITIONAL CHECKS]')

        # Общая статистика базы
        try:
            all_results = await search_service.storage_manager.search_documents(
                query="статья",
                limit=20
            )
            print(f'Total documents with "статья": {len(all_results)}')

            law_115_count = len([r for r in all_results if '115' in str(r.get('metadata', {}))])
            law_224_count = len([r for r in all_results if '224' in str(r.get('metadata', {}))])

            print(f'Law 115-FZ documents: {law_115_count}')
            print(f'Law 224-FZ documents: {law_224_count}')

        except Exception as e:
            print(f'Statistics error: {e}')

        return passed_tests >= total_tests * 0.7  # 70% успеха для валидации

    except Exception as e:
        print(f'[CRITICAL] Validation failed: {e}')
        import traceback
        traceback.print_exc()
        return False

async def test_ai_responses():
    """Дополнительный тест AI-ответов"""
    print('\n[AI RESPONSE TEST] Testing AI generation with new data...')

    try:
        search_service = SearchService()
        await search_service.initialize()

        test_questions = [
            "Что такое плата концедента?",
            "Какая статья регулирует финансовое участие концедента?",
            "Какие ограничения установлены для размера капитального гранта?"
        ]

        for question in test_questions:
            print(f'\n[Q] {question}')
            try:
                result = await search_service._handle_search_request({
                    'query': question,
                    'max_results': 3,
                    'use_cache': False
                })

                ai_response = result.get('ai_response', '')
                if ai_response:
                    print(f'[A] {ai_response[:200]}...' if len(ai_response) > 200 else f'[A] {ai_response}')
                else:
                    print('[A] No AI response generated')

            except Exception as e:
                print(f'[ERROR] {e}')

    except Exception as e:
        print(f'AI test failed: {e}')

if __name__ == '__main__':
    print('Running legal data validation...')

    success = asyncio.run(validate_critical_legal_data())

    if success:
        # Если данные валидны, тестируем AI
        asyncio.run(test_ai_responses())
        print('\n[SUCCESS] Validation completed successfully')
    else:
        print('\n[FAILED] Validation failed - data needs reindexing')