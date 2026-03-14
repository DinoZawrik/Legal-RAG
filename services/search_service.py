#!/usr/bin/env python3
"""
Search Service (Compatibility Wrapper)
Обратная совместимость для модулярной архитектуры Search Service.

УСТАРЕЛ: Этот файл является wrapper для новых модулей:
- search_service_core.py: Базовая инфраструктура и инициализация
- search_utilities.py: Утилитарные функции поиска
- search_request_handlers.py: Обработка стандартных запросов
- search_advanced_handlers.py: Продвинутые функции поиска
- search_factory.py: Фабрика и глобальное управление

Архитектурные улучшения:
- Разделение монолитного файла (1245 строк) на 5 модулей (~250-300 строк каждый)
- Четкое разделение ответственности между компонентами
- Улучшенная тестируемость и поддерживаемость
- Сохранение полной обратной совместимости

Используйте новые модули напрямую для лучшей производительности:
- from services.search_factory import SearchService, get_search_service
- from services.search_service_core import SearchServiceCore
- from services.search_request_handlers import SearchRequestHandlers
- from services.search_advanced_handlers import SearchAdvancedHandlers
- from services.search_utilities import SearchUtilities

История изменений:
- v1.0: Монолитная архитектура (search_service.py, 1245 строк)
- v2.0: Модульная архитектура с compatibility wrapper (текущая версия)
"""

import logging

# Import all classes and functions from new modular architecture
from services.search_factory import (
    SearchService,
    SearchServiceFactory,
    create_search_service,
    cleanup_global_search_service,
    test_search_service,
    run_search_service_tests,
)

from services.search_service_core import SearchServiceCore
from services.search_utilities import SearchUtilities
from services.search_request_handlers import SearchRequestHandlers
from services.search_advanced_handlers import SearchAdvancedHandlers

# Настройка логирования
logger = logging.getLogger(__name__)
search_logger = logging.getLogger("search_operations")

# Backward compatibility exports
__all__ = [
    # Core classes
    'SearchService',
    'SearchServiceCore',
    'SearchServiceFactory',

    # Handler classes
    'SearchRequestHandlers',
    'SearchAdvancedHandlers',
    'SearchUtilities',

    # Factory functions
    'create_search_service',
    'cleanup_global_search_service',

    # Testing functions
    'test_search_service',
    'run_search_service_tests'
]

# Compatibility notice for developers
logger.info(" Loading modular Search Service architecture (compatibility wrapper)")
logger.debug(f" Imported {len(__all__)} components from modular search suite")

# Architecture transition guide for developers
def _show_migration_guide():
    """Development helper showing how to migrate from old to new architecture."""
    migration_examples = {
        "Main Search Class": {
            "old": "from services.search_service import SearchService",
            "new": "from services.search_factory import SearchService"
        },
        "Core Infrastructure": {
            "old": "SearchService.initialize()",
            "new": "SearchServiceCore.initialize()"
        },
        "Request Handling": {
            "old": "SearchService._handle_search_request()",
            "new": "SearchRequestHandlers._handle_search_request()"
        },
        "Advanced Search": {
            "old": "SearchService._handle_hybrid_search_request()",
            "new": "SearchAdvancedHandlers._handle_hybrid_search_request()"
        },
        "Utility Functions": {
            "old": "SearchService._extract_key_sentences()",
            "new": "SearchUtilities._extract_key_sentences()"
        }
    }

    logger.debug(" Search Service Architecture Migration Guide:")
    for operation, examples in migration_examples.items():
        logger.debug(f" {operation}: {examples['old']} {examples['new']}")

# Show migration guide in debug mode
if logger.isEnabledFor(logging.DEBUG):
    _show_migration_guide()

# Developer migration notes
"""
MIGRATION GUIDE: From Monolithic to Modular Architecture

Old Structure (v1.0):
   services/search_service.py (1245 lines)
       SearchService class (all functionality)
       Search request handling
       Advanced search modes
       Utility functions
       Factory functions

New Structure (v2.0):
   services/search_service_core.py (~300 lines)
   SearchServiceCore class (base infrastructure)
   Component initialization
   Configuration management
   
   services/search_utilities.py (~370 lines)
   SearchUtilities class
   Text processing functions
   Legal entity extraction
   
   services/search_request_handlers.py (~350 lines)
   SearchRequestHandlers class
   Standard search processing
   Configuration and stats handling
   
   services/search_advanced_handlers.py (~440 lines)
   SearchAdvancedHandlers class
   Universal legal queries
   Hybrid search (graph + semantic)
   Multimodal search pipeline
   
   services/search_factory.py (~200 lines)
   SearchServiceFactory class
   SearchService (composite class)
   Global instance management
   Testing functions
   
   services/search_service.py (120 lines, this file)
       Compatibility wrapper

Migration Steps:
1. Replace imports:
   OLD: from services.search_service import SearchService
   NEW: from services.search_factory import SearchService

2. Use specialized components:
   OLD: service._handle_search_request()
   NEW: SearchRequestHandlers()._handle_search_request()

3. Access specific functionality:
   OLD: service._extract_key_sentences()
   NEW: SearchUtilities._extract_key_sentences()

Benefits:
- 84% code reduction per file (1245 ~200-350 lines each)
- Clear separation of concerns
- Improved testability
- Better maintainability
- Enhanced code organization

Breaking Changes: None
This wrapper maintains 100% backward compatibility.
"""

if __name__ == "__main__":
    import asyncio
    from core.logging_config import configure_logging

    configure_logging()
    asyncio.run(run_search_service_tests())
