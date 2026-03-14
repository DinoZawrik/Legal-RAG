#!/usr/bin/env python3
"""
Search Service Factory
Фабрика для создания и управления экземплярами Search Service.

Включает функциональность:
- Создание и инициализация Search Service
- Глобальное управление экземплярами
- Тестовые функции и точки входа
- Lifecycle management
"""

import asyncio
import logging
import os
from datetime import datetime

from services.search_service_core import SearchServiceCore
from services.search_request_handlers import SearchRequestHandlers
from services.search_advanced_handlers import SearchAdvancedHandlers

logger = logging.getLogger(__name__)


class SearchServiceFactory:
    """Фабрика для создания экземпляров Search Service."""

    @staticmethod
    def create_search_service() -> 'SearchService':
        """Создание нового экземпляра Search Service."""
        return SearchService()

    @staticmethod
    async def create_and_initialize_search_service() -> 'SearchService':
        """Создание и инициализация Search Service."""
        service = SearchServiceFactory.create_search_service()
        await service.initialize()
        await service.start()
        return service


class SearchService(SearchServiceCore):
    """
    Полный Search Service с композиционной архитектурой.

    Объединяет все модули поиска:
    - SearchServiceCore: базовая инфраструктура
    - SearchRequestHandlers: обработка стандартных запросов
    - SearchAdvancedHandlers: продвинутые функции поиска
    """

    def __init__(self):
        super().__init__()

        # Обработчики запросов
        self.request_handlers = None
        self.advanced_handlers = None

    async def initialize(self) -> None:
        """Инициализация Search Service."""
        try:
            # Инициализация базового сервиса
            await super().initialize()

            # Инициализация обработчиков
            self.request_handlers = SearchRequestHandlers()
            self.request_handlers.__dict__.update(self.__dict__) # Копируем состояние

            self.advanced_handlers = SearchAdvancedHandlers()
            self.advanced_handlers.__dict__.update(self.__dict__) # Копируем состояние

            self.logger.info("[FACTORY] Search Service handlers initialized")

        except Exception as e:
            self.logger.error(f"[X] Failed to initialize Search Service: {e}")
            raise

    async def process_request(self, request: dict) -> dict:
        """Обработка запросов через модульную архитектуру."""
        try:
            request_type = request.get("type", "search")

            # DEBUG: Log routing decision
            print(f"[SEARCH-FACTORY] Routing request: type={request_type}, query={request.get('query', '')[:50]}")
            self.logger.info(f"[SEARCH-FACTORY] Routing request: type={request_type}, query={request.get('query', '')[:50]}")

            # Стандартные запросы через request_handlers
            if request_type in ["search", "config", "stats", "cache"]:
                print(f"[SEARCH-FACTORY] -> Routing to request_handlers.process_request()")
                self.logger.info(f"[SEARCH-FACTORY] -> Routing to request_handlers.process_request()")
                return await self.request_handlers.process_request(request)

            # Продвинутые запросы через advanced_handlers
            elif request_type in ["universal_legal_query", "hybrid_search", "multimodal_search"]:
                # Маршрутизация к соответствующему обработчику
                if request_type == "universal_legal_query":
                    return await self.advanced_handlers._handle_universal_legal_query(request)
                elif request_type == "hybrid_search":
                    return await self.advanced_handlers._handle_hybrid_search_request(request)
                elif request_type == "multimodal_search":
                    return await self.advanced_handlers._handle_multimodal_search_request(request)

            else:
                return {
                    "success": False,
                    "error": f"Unknown request type: {request_type}",
                    "supported_types": [
                        "search", "universal_legal_query", "hybrid_search",
                        "multimodal_search", "config", "stats", "cache"
                    ],
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            self.logger.error(f"[X] Error processing request: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


async def create_search_service() -> SearchService:
    """Создание нового экземпляра Search Service."""
    return await SearchServiceFactory.create_and_initialize_search_service()


async def cleanup_global_search_service() -> None:
    """Совместимость: сохранена для старых вызовов (ничего не делает)."""
    return


# Тестовые функции
async def test_search_service():
    """Тестирование Search Service."""
    print("[SEARCH] Testing Search Service")

    service = SearchService()
    await service.initialize()
    await service.start()

    try:
        # Тест стандартного поиска
        test_request = {
            "type": "search",
            "query": "теплоснабжение жилых домов",
            "max_results": 5,
            "use_cache": True
        }

        response = await service.process_request(test_request)
        success = response.get('success', False)
        results_count = len(response.get('results', []))
        print(f"[CHECK_MARK_BUTTON] Standard search test: success={success}, results={results_count}")

        # Тест конфигурации
        config_request = {"type": "config", "action": "get"}
        config_response = await service.process_request(config_request)
        print(f"[CHECK_MARK_BUTTON] Config test: success={config_response.get('success', False)}")

        # Тест статистики
        stats_request = {"type": "stats"}
        stats_response = await service.process_request(stats_request)
        print(f"[CHECK_MARK_BUTTON] Stats test: success={stats_response.get('success', False)}")

        # Тест универсального правового запроса (если доступен)
        if service.universal_legal_system:
            universal_request = {
                "type": "universal_legal_query",
                "query": "теплоснабжение жилых домов",
                "max_chunks": 5
            }
            universal_response = await service.process_request(universal_request)
            print(f"[CHECK_MARK_BUTTON] Universal legal query test: success={universal_response.get('success', False)}")

        # Тест гибридного поиска (если доступен)
        if service.hybrid_storage:
            hybrid_request = {
                "type": "hybrid_search",
                "query": "теплоснабжение жилых домов",
                "max_results": 5,
                "graph_enabled": True
            }
            hybrid_response = await service.process_request(hybrid_request)
            print(f"[CHECK_MARK_BUTTON] Hybrid search test: success={hybrid_response.get('success', False)}")

        print("[CHECK_MARK_BUTTON] All tests completed successfully")

    except Exception as e:
        print(f"[X] Test failed: {e}")
        raise

    finally:
        await service.cleanup()
        await service.stop()


async def run_search_service_tests():
    """Запуск тестов Search Service."""
    try:
        await test_search_service()
    except Exception as e:
        print(f"[X] Search Service tests failed: {e}")
        raise


if __name__ == "__main__":
    # Прямое выполнение файла запускает тесты
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))

    asyncio.run(run_search_service_tests())