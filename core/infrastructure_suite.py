#!/usr/bin/env python3
"""
🏗️ Core Infrastructure Suite (Compatibility Wrapper)
Обратная совместимость для модулярной архитектуры Core Infrastructure Suite.

УСТАРЕЛ: Этот файл является wrapper для новых модулей:
- infrastructure_core.py: Основное приложение и координация инфраструктуры
- infrastructure_models.py: Модели данных, enums, Pydantic и dataclass модели
- infrastructure_utilities.py: Системные утилиты, PDF обработка, LLM клиент
- infrastructure_database.py: Управление БД и миграциями

Архитектурные улучшения:
- Разделение монолитного файла (915 строк) на 4 модуля (~250-320 строк каждый)
- Четкое разделение ответственности между компонентами
- Улучшенная тестируемость и поддерживаемость
- Сохранение полной обратной совместимости
- КРИТИЧЕСКОЕ ТРЕБОВАНИЕ: Использование ТОЛЬКО документов БД (complex_task.txt)

Используйте новые модули напрямую для лучшей производительности:
- from core.infrastructure_core import CoreApplication, create_document
- from core.infrastructure_models import Document, DocumentType, ProcessingStatus
- from core.infrastructure_utilities import SystemUtilities
- from core.infrastructure_database import DatabaseMigrations

История изменений:
- v1.0: Монолитная архитектура (infrastructure_suite.py, 915 строк)
- v2.0: Модульная архитектура с compatibility wrapper (текущая версия)
"""

import logging
from typing import Dict, List, Optional, Any

# Import all classes and functions from new modular architecture
from core.infrastructure_core import (
    CoreApplication,
    get_core_app,
    get_utilities,
    get_migrations,
    initialize_core_system,
    create_document,
    create_processing_task,
    create_contextual_chunk_for_database,
    verify_system_compliance
)

from core.infrastructure_models import (
    # Enums
    DocumentType,
    ProcessingStatus,

    # Pydantic models
    ValidationReport,
    SpatialElement,
    ElementRelationship,
    ContextualData,
    PageLayout,
    ContextualExtraction,
    ParsedTable,
    ParsedPageTables,

    # Dataclass models
    TextChunk,
    TableChunk,
    AnyChunk,
    ExtractedData,
    RegulatoryDocument,
    Document,
    ProcessingTask,
    ProcessingState,
    ContextualChunk,

    # LangGraph state
    IngestionState
)

from core.infrastructure_utilities import (
    SystemUtilities,
    get_system_utilities,
    validate_file_for_database,
    extract_pdf_content_for_database,
    create_document_hash
)

from core.infrastructure_database import (
    DatabaseMigrations,
    get_database_migrations,
    setup_database_schema,
    verify_database_requirements
)

# Import settings compatibility
from core.settings import get_settings, SETTINGS

# Настройка логирования
logger = logging.getLogger(__name__)


# Backward compatibility exports
__all__ = [
    # Core classes
    'CoreApplication',
    'SystemUtilities',
    'DatabaseMigrations',

    # Enums
    'DocumentType',
    'ProcessingStatus',

    # Pydantic models
    'ValidationReport',
    'SpatialElement',
    'ElementRelationship',
    'ContextualData',
    'PageLayout',
    'ContextualExtraction',
    'ParsedTable',
    'ParsedPageTables',

    # Dataclass models
    'TextChunk',
    'TableChunk',
    'AnyChunk',
    'ExtractedData',
    'RegulatoryDocument',
    'Document',
    'ProcessingTask',
    'ProcessingState',
    'ContextualChunk',
    'IngestionState',

    # Factory functions
    'create_document',
    'create_processing_task',
    'create_contextual_chunk_for_database',
    'get_core_app',
    'get_utilities',
    'get_migrations',
    'get_settings',
    'SETTINGS',
    'initialize_core_system',
    'verify_system_compliance',

    # Database functions
    'setup_database_schema',
    'verify_database_requirements',

    # Utility functions
    'validate_file_for_database',
    'extract_pdf_content_for_database',
    'create_document_hash'
]

# Compatibility notice for developers
logger.info("📦 Loading modular Infrastructure Suite architecture (compatibility wrapper)")
logger.debug(f"✅ Imported {len(__all__)} components from modular Infrastructure suite")

# Architecture transition guide for developers
def _show_migration_guide():
    """Development helper showing how to migrate from old to new architecture."""
    migration_examples = {
        "Core Application": {
            "old": "from core.infrastructure_suite import CoreApplication",
            "new": "from core.infrastructure_core import CoreApplication"
        },
        "Data Models": {
            "old": "from core.infrastructure_suite import Document, DocumentType",
            "new": "from core.infrastructure_models import Document, DocumentType"
        },
        "System Utilities": {
            "old": "from core.infrastructure_suite import SystemUtilities",
            "new": "from core.infrastructure_utilities import SystemUtilities"
        },
        "Database Migrations": {
            "old": "from core.infrastructure_suite import DatabaseMigrations",
            "new": "from core.infrastructure_database import DatabaseMigrations"
        }
    }

    logger.debug("🔄 Infrastructure Suite Architecture Migration Guide:")
    for operation, examples in migration_examples.items():
        logger.debug(f"  {operation}: {examples['old']} → {examples['new']}")

# Show migration guide in debug mode
if logger.isEnabledFor(logging.DEBUG):
    _show_migration_guide()


# Global instances for compatibility
core_app = get_core_app()
utilities = get_utilities()
migrations = get_migrations()


# Developer migration notes
"""
📋 MIGRATION GUIDE: From Monolithic to Modular Architecture

🗂️ Old Structure (v1.0):
   └── core/infrastructure_suite.py (915 lines)
       ├── CoreApplication class
       ├── SystemUtilities class
       ├── DatabaseMigrations class
       ├── All data models and enums
       └── Convenience functions

🎯 New Structure (v2.0):
   ├── core/infrastructure_core.py (~320 lines)
   │   ├── CoreApplication class
   │   ├── Document processing for database
   │   ├── System compliance verification
   │   └── Application lifecycle management
   │
   ├── core/infrastructure_models.py (~330 lines)
   │   ├── DocumentType, ProcessingStatus enums
   │   ├── Pydantic models for validation
   │   ├── Dataclass models for documents
   │   └── LangGraph workflow states
   │
   ├── core/infrastructure_utilities.py (~280 lines)
   │   ├── SystemUtilities class
   │   ├── PDF text extraction
   │   ├── File validation and hashing
   │   └── LLM client management
   │
   ├── core/infrastructure_database.py (~280 lines)
   │   ├── DatabaseMigrations class
   │   ├── Table schema definitions
   │   ├── Migration management
   │   └── Database verification
   │
   └── core/infrastructure_suite.py (~150 lines, this file)
       └── Compatibility wrapper

🔄 Migration Steps:
1. Replace imports:
   OLD: from core.infrastructure_suite import CoreApplication
   NEW: from core.infrastructure_core import CoreApplication

2. Use specialized components:
   OLD: from core.infrastructure_suite import SystemUtilities
   NEW: from core.infrastructure_utilities import SystemUtilities

3. Access specific functionality:
   OLD: from core.infrastructure_suite import Document, DocumentType
   NEW: from core.infrastructure_models import Document, DocumentType

📈 Benefits:
- 84% code reduction per file (915 → ~150-330 lines each)
- Clear separation of concerns
- Improved testability
- Better maintainability
- Enhanced code organization
- CRITICAL: Emphasis on database-only document processing (complex_task.txt requirement)

⚠️ Breaking Changes: None
This wrapper maintains 100% backward compatibility.

🚨 ВАЖНОЕ ТРЕБОВАНИЕ из complex_task.txt:
Система должна использовать ТОЛЬКО документы из БД, а НЕ собственные знания модели!
Все компоненты подчеркивают это требование через логирование и метаданные.
"""

if __name__ == "__main__":
    # Direct execution still works through main import
    import asyncio
    from core.logging_config import configure_logging

    configure_logging()

    async def test_modular_infrastructure():
        """Тестирование модульной инфраструктуры."""
        logger.info("🧪 Тестирование модульной Infrastructure Suite...")

        try:
            # Создание системы
            app = await initialize_core_system()
            status = app.get_status()

            logger.info(f"✅ Система инициализирована: {status['initialized']}")
            logger.info(f"🔧 Компонентов: {len(status['components'])}")
            logger.info(f"⚙️ Настройки: Debug={status['settings']['debug']}")

            # Проверка соответствия требованиям
            compliance = await verify_system_compliance()
            logger.info(f"📋 Соответствие БД требованиям: {compliance['database_documents_only']}")
            logger.info("✨ Модульная инфраструктура работает корректно!")

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования: {e}")

    asyncio.run(test_modular_infrastructure())