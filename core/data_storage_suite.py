#!/usr/bin/env python3
"""
📦 Storage Suite Compatibility Layer

Этот модуль сохраняет обратную совместимость для старых импортов,
перенаправляя их на новый `StorageCoordinator`.
"""

import logging
import warnings
from typing import Optional, List, Dict, Any

from core.infrastructure_suite import SETTINGS, TextChunk
from core.postgres_manager import (
    PostgresManager,
    DatabaseError,
    get_ssl_config,
    create_postgres_manager,
)
from core.redis_manager import (
    RedisManager,
    create_redis_manager,
)
from core.vector_store_manager import (
    VectorStoreManager,
    create_vector_store,
    add_documents_to_vector_store,
)
from core.storage_coordinator import StorageCoordinator, create_storage_coordinator

logger = logging.getLogger(__name__)


warnings.warn(
    "core.data_storage_suite устаревает. Используйте core.storage_coordinator.StorageCoordinator",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    # Core manager classes
    "PostgresManager",
    "RedisManager",
    "VectorStoreManager",
    "StorageCoordinator",
    "UnifiedStorageManager",
    # Exception classes
    "DatabaseError",
    # Factory functions
    "create_postgres_manager",
    "create_redis_manager",
    "create_vector_store",
    "create_unified_storage",
    # Utility exports
    "get_ssl_config",
    "get_redis_client",
    "update_task_status",
    "add_documents_to_vector_store",
    # Shared components
    "SETTINGS",
    "TextChunk",
]

# Legacy name still used по всему коду
UnifiedStorageManager = StorageCoordinator

async def create_unified_storage() -> StorageCoordinator:
    """Create new coordinator instance (compat wrapper)."""

    warnings.warn(
        "create_unified_storage устаревает. Используйте core.storage_coordinator.create_storage_coordinator",
        DeprecationWarning,
        stacklevel=2,
    )
    return await create_storage_coordinator()


def get_redis_client():
    """Синхронный Redis клиент (используется телеграм-ботом)."""

    global redis_manager

    if redis_manager and redis_manager.sync_client:
        return redis_manager.sync_client

    try:
        manager = create_redis_manager()
        redis_manager = manager
        if not manager.sync_client:
            raise RuntimeError("RedisManager не инициализирован")
        return manager.sync_client
    except Exception as exc:  # pragma: no cover - окружение может отсутствовать
        logger.error("❌ Ошибка создания Redis клиента: %s", exc)
        return None


async def update_task_status(task_id: str, status: str, message: str = "", progress: int = 0) -> bool:
    """Обновление статуса задач через Redis (совместимость)."""

    global redis_manager

    try:
        if redis_manager is None or redis_manager.client is None:
            redis_manager = create_redis_manager()
            await redis_manager.initialize()

        return await redis_manager.update_task_status(task_id, status, message, progress)
    except Exception as exc:
        logger.error("❌ Ошибка обновления статуса задачи %s: %s", task_id, exc)
        return False


async def add_documents_to_vector_store_compat(vector_store, chunks):
    """Совместимость: проксирует в новый helper из vector_store_manager."""

    return await add_documents_to_vector_store(vector_store, chunks)


# Сохраняем оригинальные имена функций, которые использовались ранее
add_documents_to_vector_store = add_documents_to_vector_store_compat