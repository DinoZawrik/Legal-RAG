#!/usr/bin/env python3
"""
Диагностика проблемы парсинга JSON в API Gateway
"""

import json
import asyncio
import aiohttp
from pydantic import BaseModel
from typing import Optional, Dict, Any

class QueryRequest(BaseModel):
    """Тест модели запроса."""
    query: str
    max_results: Optional[int] = 10
    use_cache: Optional[bool] = True
    config: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None

async def test_json_parsing():
    """Тестируем парсинг JSON напрямую"""
    print("ДИАГНОСТИКА ПРОБЛЕМЫ ПАРСИНГА JSON")
    print("=" * 50)

    # 1. Тест создания модели напрямую
    try:
        test_data = {
            "query": "плата концедента",
            "max_results": 3
        }

        print("1. Тест создания модели Pydantic:")
        request = QueryRequest(**test_data)
        print(f"   OK Модель создана: {request}")
        print(f"   Query: {request.query}")
        print(f"   Max results: {request.max_results}")
    except Exception as e:
        print(f"   ERROR Ошибка создания модели: {e}")
        return False

    # 2. Тест JSON serialization
    try:
        print("\n2. Тест JSON сериализации:")
        json_str = json.dumps(test_data, ensure_ascii=False)
        print(f"   JSON строка: {json_str}")

        parsed_back = json.loads(json_str)
        print(f"   OK JSON корректно парсится: {parsed_back}")
    except Exception as e:
        print(f"   ERROR Ошибка JSON: {e}")
        return False

    # 3. Тест HTTP запроса
    try:
        print("\n3. Тест HTTP запроса к API:")
        async with aiohttp.ClientSession() as session:
            # Проверим простейший endpoint
            async with session.get("http://localhost:8080/health") as response:
                print(f"   Health endpoint status: {response.status}")
                if response.status == 200:
                    result = await response.json()
                    print(f"   OK Health OK: {result.get('status')}")
                else:
                    print(f"   ERROR Health failed: {response.status}")
                    return False
    except Exception as e:
        print(f"   ERROR Ошибка HTTP: {e}")
        return False

    # 4. Тест простого JSON POST
    try:
        print("\n4. Тест простого JSON POST:")
        async with aiohttp.ClientSession() as session:
            headers = {'Content-Type': 'application/json'}

            async with session.post(
                "http://localhost:8080/api/query",
                json=test_data,
                headers=headers,
                timeout=10
            ) as response:
                print(f"   POST status: {response.status}")
                response_text = await response.text()
                print(f"   Response: {response_text[:200]}...")

                if response.status == 200:
                    print("   OK JSON POST работает!")
                    return True
                else:
                    print(f"   ERROR JSON POST failed: {response.status}")
                    print(f"   Error details: {response_text}")
                    return False
    except Exception as e:
        print(f"   ERROR Ошибка POST: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_json_parsing())