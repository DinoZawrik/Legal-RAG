#!/usr/bin/env python3
"""
🗄️ Redis Cache Manager
Модуль для работы с Redis кэшированием и очередью задач.

Включает функциональность:
- Подключение к Redis
- Кэширование данных
- Отслеживание статуса задач
- Pub/Sub операции
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any

# Core imports
from core.infrastructure_suite import SETTINGS

# External imports
try:
    import redis.asyncio as aioredis
    import redis
except ImportError as e:
    logging.warning(f"Redis dependencies not available: {e}")

logger = logging.getLogger(__name__)


class RedisManager:
    """
    Менеджер для работы с Redis.
    Объединяет функциональность из redis_utils.py
    """

    def __init__(self):
        self.client: Optional[aioredis.Redis] = None
        self.sync_client: Optional[redis.Redis] = None

    async def initialize(self) -> bool:
        """Инициализация подключения к Redis."""
        try:
            # Async клиент
            self.client = aioredis.from_url(
                f"redis://{SETTINGS.REDIS_HOST}:{SETTINGS.REDIS_PORT}/{SETTINGS.REDIS_DB}",
                decode_responses=True
            )

            # Sync клиент для некоторых операций
            self.sync_client = redis.Redis(
                host=SETTINGS.REDIS_HOST,
                port=SETTINGS.REDIS_PORT,
                db=SETTINGS.REDIS_DB,
                decode_responses=True
            )

            # Проверка соединения
            await self.client.ping()

            logger.info("✅ Redis подключение инициализировано")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Redis: {e}")
            return False

    async def close(self):
        """Закрытие соединений."""
        if self.client:
            await self.client.close()
        if self.sync_client:
            self.sync_client.close()
        logger.info("🔒 Redis соединения закрыты")

    async def set_cache(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Установка значения в кэш."""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)

            await self.client.setex(key, expire, value)
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка установки кэша {key}: {e}")
            return False

    async def get_cache(self, key: str) -> Optional[Any]:
        """Получение значения из кэша."""
        try:
            value = await self.client.get(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения кэша {key}: {e}")
            return None

    async def update_task_status(self, task_id: str, status: str,
                               message: str = "", progress: int = 0) -> bool:
        """Обновление статуса задачи."""
        try:
            task_data = {
                "task_id": task_id,
                "status": status,
                "message": message,
                "progress": progress,
                "updated_at": datetime.now().isoformat()
            }

            key = f"task:{task_id}"
            await self.client.setex(key, 3600, json.dumps(task_data))

            # Публикация обновления
            await self.client.publish(f"task_updates:{task_id}", json.dumps(task_data))

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса задачи {task_id}: {e}")
            return False

    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Получение статуса задачи."""
        try:
            key = f"task:{task_id}"
            data = await self.client.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения статуса задачи {task_id}: {e}")
            return None

    async def delete_cache(self, key: str) -> bool:
        """Удаление значения из кэша."""
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления кэша {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Проверка существования ключа в кэше."""
        try:
            result = await self.client.exists(key)
            return bool(result)
        except Exception as e:
            logger.error(f"❌ Ошибка проверки существования кэша {key}: {e}")
            return False

    async def increment(self, key: str) -> int:
        """Инкремент числового значения в кэше."""
        try:
            return await self.client.incr(key)
        except Exception as e:
            logger.error(f"❌ Ошибка инкремента кэша {key}: {e}")
            return 0

    async def get_all_task_statuses(self) -> Dict[str, Dict]:
        """Получение всех статусов задач."""
        try:
            keys = await self.client.keys("task:*")
            statuses = {}

            for key in keys:
                task_id = key.replace("task:", "")
                status_data = await self.get_task_status(task_id)
                if status_data:
                    statuses[task_id] = status_data

            return statuses
        except Exception as e:
            logger.error(f"❌ Ошибка получения всех статусов задач: {e}")
            return {}


def create_redis_manager() -> RedisManager:
    """Factory function для создания RedisManager."""
    return RedisManager()


def get_redis_client() -> Optional[redis.Redis]:
    """Utility function для получения синхронного Redis клиента."""
    try:
        return redis.Redis(
            host=SETTINGS.REDIS_HOST,
            port=SETTINGS.REDIS_PORT,
            db=SETTINGS.REDIS_DB,
            decode_responses=True
        )
    except Exception as e:
        logger.error(f"❌ Ошибка создания Redis клиента: {e}")
        return None


# Compatibility wrapper for legacy code
async def update_task_status(task_id: str, status: str, message: str = "", progress: int = 0) -> bool:
    """Compatibility wrapper для обновления статуса задач."""
    manager = create_redis_manager()
    await manager.initialize()
    result = await manager.update_task_status(task_id, status, message, progress)
    await manager.close()
    return result