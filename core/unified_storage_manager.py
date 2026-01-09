#!/usr/bin/env python3
"""
🗄️ Unified Storage Manager
Модуль для координации всех типов хранилищ.

Включает функциональность:
- Объединенный интерфейс для PostgreSQL, Redis, ChromaDB
- Управление полным циклом сохранения документов
- Глобальные экземпляры и фабричные функции
- Совместимость с legacy кодом
"""

import hashlib
import logging
import os
import warnings
from datetime import datetime
from typing import Dict, List, Optional, Any

# Core imports
from core.infrastructure_suite import SETTINGS, TextChunk
from core.postgres_manager import PostgresManager, DatabaseError
from core.redis_manager import RedisManager
from core.vector_store_manager import VectorStoreManager

logger = logging.getLogger(__name__)

warnings.warn(
    "core.unified_storage_manager устаревает. Используйте core.storage_coordinator.StorageCoordinator",
    DeprecationWarning,
    stacklevel=2,
)


class UnifiedStorageManager:
    """
    Объединенный менеджер для всех типов хранилищ.
    Комбинирует PostgreSQL, Redis и Vector Store.
    """

    def __init__(self):
        self.postgres = PostgresManager()
        self.redis = RedisManager()
        self.vector_store = VectorStoreManager()

    async def initialize(self) -> Dict[str, bool]:
        """Инициализация всех хранилищ."""
        results = {}

        try:
            results['postgres'] = await self.postgres.initialize()
            results['redis'] = await self.redis.initialize()
            results['vector_store'] = await self.vector_store.initialize()

            success_count = sum(results.values())
            total_count = len(results)

            if success_count == total_count:
                logger.info("✅ Все хранилища инициализированы успешно")
            else:
                logger.warning(f"⚠️ Инициализировано {success_count}/{total_count} хранилищ")

            return results

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации хранилищ: {e}")
            return results

    async def close_all(self):
        """Закрытие всех соединений."""
        await self.postgres.close()
        await self.redis.close()
        logger.info("🔒 Все соединения хранилищ закрыты")

    async def store_document_complete(self, file_path: str, chunks: List[TextChunk],
                                   metadata: Dict = None) -> Dict[str, Any]:
        """Полное сохранение документа во все хранилища."""
        try:
            # Проверяем параметр принудительной переобработки
            force_reprocess = metadata.get('force_reprocess', False) if metadata else False

            # Подготовка данных документа (без заранее заданного ID)
            file_path_obj = os.path.abspath(file_path)

            # Вычисление хеша файла
            file_hash = None
            file_size = None
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    content = f.read()
                    file_hash = hashlib.sha256(content).hexdigest()
                    file_size = len(content)

            # Use original filename from metadata if available, otherwise use file path
            original_filename = None
            if metadata and 'original_filename' in metadata:
                original_filename = metadata['original_filename']
            elif metadata and 'filename' in metadata:
                original_filename = metadata['filename']
            else:
                original_filename = os.path.basename(file_path)

            document_data = {
                'file_path': file_path_obj,
                'file_name': original_filename,
                'file_size': file_size,
                'file_hash': file_hash,
                'document_type': metadata.get('document_type', 'general') if metadata else 'general',
                'processed_at': datetime.now(),
                'status': 'completed',
                'metadata': metadata or {}
            }

            # Сохранение в PostgreSQL (получаем реальный ID из базы)
            # При force_reprocess пропускаем проверку дубликатов
            if force_reprocess:
                logger.info(f"🔄 Принудительная переобработка: пропускаем проверку дубликатов для {original_filename}")
                doc_id, is_duplicate = await self.postgres.insert_document(document_data, skip_duplicates=True)
            else:
                doc_id, is_duplicate = await self.postgres.insert_document(document_data)

            # Если документ - дубликат, не обрабатываем чанки повторно
            if is_duplicate:
                logger.info(f"⏭️ Пропускаем обработку чанков для дубликата: {original_filename}")
                return {
                    "success": True,
                    "document_id": doc_id,
                    "duplicate": True,
                    "message": f"Документ '{original_filename}' уже существует в системе"
                }

            # Сохранение чанков только в ChromaDB (векторное хранилище)
            if chunks:
                await self.vector_store.add_documents(chunks)

            # Кэширование в Redis (подготавливаем данные для JSON)
            cache_data = document_data.copy()
            if 'processed_at' in cache_data and cache_data['processed_at']:
                cache_data['processed_at'] = cache_data['processed_at'].isoformat()

            try:
                cache_key = f"document:{doc_id}"
                await self.redis.set_cache(cache_key, cache_data, expire=86400)  # 24 часа
            except Exception as e:
                logger.warning(f"❌ Ошибка установки кэша {cache_key}: {e}")

            result = {
                'success': True,
                'document_id': doc_id,
                'duplicate': False,
                'chunks_stored': len(chunks) if chunks else 0,
                'file_hash': file_hash,
                'storage_locations': ['vector_store', 'redis_cache']
            }

            logger.info(f"✅ Документ {doc_id} полностью сохранен")
            return result

        except Exception as e:
            logger.error(f"❌ Ошибка полного сохранения документа: {e}")
            return {
                'success': False,
                'error': str(e),
                'document_id': None
            }

    async def search_documents(self, query: str, limit: Optional[int] = None,
                             use_cache: bool = True, max_results: Optional[int] = None,
                             graph_enabled: Optional[bool] = None, **kwargs) -> List[Dict]:
        """Поиск документов с поддержкой расширенных параметров."""
        try:
            effective_limit = max_results if max_results is not None else limit
            if effective_limit is None or effective_limit <= 0:
                effective_limit = 10

            # Формируем ключ кэша с учетом дополнительных параметров
            cache_key_parts = [
                hashlib.md5(query.encode()).hexdigest(),
                str(effective_limit)
            ]
            if graph_enabled is not None:
                cache_key_parts.append(f"graph:{int(bool(graph_enabled))}")

            cache_key = "search:" + ":".join(cache_key_parts)

            cached_results = None
            if use_cache:
                try:
                    cached_results = await self.redis.get_cache(cache_key)
                except Exception as cache_error:
                    logger.warning(f"⚠️ Ошибка доступа к кэшу {cache_key}: {cache_error}")

            if cached_results:
                logger.info("🎯 Найдены кэшированные результаты для запроса")
                return cached_results

            # Поиск в vector store
            results = await self.vector_store.search_similar(query, effective_limit)

            # Кэширование результатов
            if use_cache and results:
                try:
                    await self.redis.set_cache(cache_key, results, expire=1800)  # 30 минут
                except Exception as cache_error:
                    logger.warning(f"⚠️ Не удалось сохранить результаты в кэш {cache_key}: {cache_error}")

            return results

        except Exception as e:
            logger.error(f"❌ Ошибка поиска документов: {e}")
            return []

    def get_health_status(self) -> Dict[str, Any]:
        """Получение статуса здоровья всех хранилищ."""
        return {
            'postgres': {
                'connected': self.postgres.pool is not None,
                'pool_size': len(self.postgres.pool._holders) if self.postgres.pool else 0
            },
            'redis': {
                'connected': self.redis.client is not None
            },
            'vector_store': {
                'connected': self.vector_store.collection is not None,
                'stats': self.vector_store.get_collection_stats()
            }
        }


# Factory functions для создания менеджеров
async def create_postgres_manager() -> PostgresManager:
    """Создание менеджера PostgreSQL."""
    manager = PostgresManager()
    await manager.initialize()
    return manager


async def create_redis_manager() -> RedisManager:
    """Создание менеджера Redis."""
    manager = RedisManager()
    await manager.initialize()
    return manager


async def create_vector_store() -> VectorStoreManager:
    """Создание менеджера vector store."""
    manager = VectorStoreManager()
    await manager.initialize()
    return manager


async def create_unified_storage() -> UnifiedStorageManager:
    """Создание объединенного менеджера хранилищ."""
    manager = UnifiedStorageManager()
    await manager.initialize()
    return manager


def get_redis_client():
    """Получение синхронного Redis клиента для использования в боте."""
    global redis_manager

    if redis_manager and redis_manager.sync_client:
        return redis_manager.sync_client

    # Если менеджер не инициализирован, создаем простой клиент
    try:
        import redis
        client = redis.Redis(
            host=SETTINGS.REDIS_HOST,
            port=SETTINGS.REDIS_PORT,
            db=SETTINGS.REDIS_DB,
            decode_responses=True
        )
        return client
    except Exception as e:
        logger.error(f"❌ Ошибка создания Redis клиента: {e}")
        return None


# ===== COMPATIBILITY FUNCTIONS =====
# Функции-обертки для совместимости с устаревшими модулями

async def add_documents_to_vector_store(vector_store, chunks):
    """Обертка для совместимости с устаревшим storage_indexing.py"""
    if hasattr(vector_store, 'add_documents'):
        return await vector_store.add_documents(chunks)
    else:
        logger.error("❌ Vector store не поддерживает add_documents")
        return False


async def update_task_status(task_id: str, status: str, progress: int = None):
    """Обертка для обновления статуса задач через Redis"""
    try:
        redis_client = get_redis_client()
        if redis_client:
            task_data = {
                'status': status,
                'updated_at': datetime.now().isoformat()
            }
            if progress is not None:
                task_data['progress'] = progress

            redis_client.hset(f"task:{task_id}", mapping=task_data)
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка обновления статуса задачи {task_id}: {e}")
    return False