"""Модуль расширений для работы с Redis в Telegram боте"""

import json
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from core.data_storage_suite import RedisManager


logger = logging.getLogger(__name__)


class RedisExtensions:
    """
    Расширения для работы с Redis, специфичные для Telegram-бота.
    Использует централизованный RedisManager для всех операций.
    """

    def __init__(self, redis_manager: RedisManager):
        """
        Инициализация расширений Redis.

        Args:
            redis_manager: Экземпляр централизованного менеджера Redis.
        """
        self.redis_manager = redis_manager
        self.redis = self.redis_manager.client

    async def delete_pattern(self, pattern: str) -> int:
        """
        Удаляет все ключи, соответствующие паттерну.

        Args:
            pattern: Паттерн для поиска ключей.

        Returns:
            int: Количество удаленных ключей.
        """
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"Ошибка при удалении ключей по паттерну {pattern}: {e}")
            return 0

    async def increment_with_ttl(self, key: str, amount: int = 1, ttl: int = 3600) -> int:
        """
        Инкрементирует значение с установкой TTL.

        Args:
            key: Ключ.
            amount: Значение для инкремента.
            ttl: Время жизни в секундах.

        Returns:
            int: Новое значение.
        """
        try:
            # Используем транзакцию для атомарности
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.incrby(key, amount)
                pipe.expire(key, ttl)
                result = await pipe.execute()
            return result
        except Exception as e:
            logger.error(f"Ошибка при инкременте значения с TTL для ключа {key}: {e}")
            return 0

    async def lock_key(self, key: str, timeout: int = 30) -> bool:
        """
        Создает блокировку для ключа (mutex).

        Args:
            key: Ключ для блокировки.
            timeout: Таймаут блокировки в секундах.

        Returns:
            bool: Успешность установки блокировки.
        """
        try:
            lock_key = f"lock:{key}"
            return await self.redis.set(lock_key, "locked", nx=True, ex=timeout)
        except Exception as e:
            logger.error(f"Ошибка при установке блокировки для ключа {key}: {e}")
            return False

    async def unlock_key(self, key: str) -> bool:
        """
        Снимает блокировку с ключа.

        Args:
            key: Ключ для разблокировки.

        Returns:
            bool: Успешность снятия блокировки.
        """
        try:
            lock_key = f"lock:{key}"
            result = await self.redis.delete(lock_key)
            return result > 0
        except Exception as e:
            logger.error(f"Ошибка при снятии блокировки с ключа {key}: {e}")
            return False

    async def get_keys_by_pattern(self, pattern: str) -> List[str]:
        """
        Получает все ключи, соответствующие паттерну.

        Args:
            pattern: Паттерн для поиска ключей.

        Returns:
            List[str]: Список ключей.
        """
        try:
            return await self.redis.keys(pattern)
        except Exception as e:
            logger.error(f"Ошибка при поиске ключей по паттерну {pattern}: {e}")
            return []

    async def cache_search_results(self, user_id: int, search_query: str, results: List[Dict], ttl: int = 1800) -> bool:
        """
        Кэширует результаты поиска для пользователя.

        Args:
            user_id: ID пользователя.
            search_query: Поисковый запрос.
            results: Результаты поиска.
            ttl: Время жизни кэша в секундах.

        Returns:
            bool: Успешность операции.
        """
        try:
            cache_key = f"search_cache:{user_id}:{hash(search_query)}"
            return await self.redis_manager.set_cache(cache_key, results, expire=ttl)
        except Exception as e:
            logger.error(f"Ошибка при кэшировании результатов поиска: {e}")
            return False

    async def get_cached_search_results(self, user_id: int, search_query: str) -> Optional[List[Dict]]:
        """
        Получает кэшированные результаты поиска.

        Args:
            user_id: ID пользователя.
            search_query: Поисковый запрос.

        Returns:
            List[Dict]: Кэшированные результаты или None.
        """
        try:
            cache_key = f"search_cache:{user_id}:{hash(search_query)}"
            return await self.redis_manager.get_cache(cache_key)
        except Exception as e:
            logger.error(f"Ошибка при получении кэшированных результатов поиска: {e}")
            return None

    async def track_user_activity(self, user_id: int, action: str) -> bool:
        """
        Отслеживает активность пользователя.

        Args:
            user_id: ID пользователя.
            action: Действие пользователя.

        Returns:
            bool: Успешность операции.
        """
        try:
            activity_key = f"user_activity:{user_id}"
            timestamp = datetime.now().isoformat()
            activity_data = {"action": action, "timestamp": timestamp}
            
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.lpush(activity_key, json.dumps(activity_data, ensure_ascii=False))
                pipe.ltrim(activity_key, 0, 99)
                pipe.expire(activity_key, 30 * 24 * 60 * 60) # 30 дней
                await pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Ошибка при отслеживании активности пользователя {user_id}: {e}")
            return False

    async def get_user_recent_activity(self, user_id: int, limit: int = 10) -> List[Dict]:
        """
        Получает последние действия пользователя.

        Args:
            user_id: ID пользователя.
            limit: Максимальное количество действий.

        Returns:
            List[Dict]: Список последних действий.
        """
        try:
            activity_key = f"user_activity:{user_id}"
            activities = await self.redis.lrange(activity_key, 0, limit - 1)
            return [json.loads(activity) for activity in activities]
        except Exception as e:
            logger.error(f"Ошибка при получении активности пользователя {user_id}: {e}")
            return []

    async def set_user_preference(self, user_id: int, preference_key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Устанавливает пользовательские предпочтения.

        Args:
            user_id: ID пользователя.
            preference_key: Ключ предпочтения.
            value: Значение предпочтения.
            ttl: Время жизни в секундах (опционально).

        Returns:
            bool: Успешность операции.
        """
        try:
            pref_key = f"user_pref:{user_id}:{preference_key}"
            expire = ttl if ttl is not None else 30 * 24 * 60 * 60 # 30 дней по умолчанию
            return await self.redis_manager.set_cache(pref_key, value, expire=expire)
        except Exception as e:
            logger.error(f"Ошибка при установке предпочтения пользователя {user_id}: {e}")
            return False

    async def get_user_preference(self, user_id: int, preference_key: str) -> Optional[Any]:
        """
        Получает пользовательские предпочтения.

        Args:
            user_id: ID пользователя.
            preference_key: Ключ предпочтения.

        Returns:
            Any: Значение предпочтения или None.
        """
        try:
            pref_key = f"user_pref:{user_id}:{preference_key}"
            return await self.redis_manager.get_cache(pref_key)
        except Exception as e:
            logger.error(f"Ошибка при получении предпочтения пользователя {user_id}: {e}")
            return None

    async def increment_user_statistic(self, user_id: int, stat_key: str, amount: int = 1) -> int:
        """
        Инкрементирует пользовательскую статистику.

        Args:
            user_id: ID пользователя.
            stat_key: Ключ статистики.
            amount: Значение для инкремента.

        Returns:
            int: Новое значение статистики.
        """
        try:
            stat_key_redis = f"user_stat:{user_id}:{stat_key}"
            return await self.increment_with_ttl(stat_key_redis, amount, 30 * 24 * 60 * 60)  # 30 дней
        except Exception as e:
            logger.error(f"Ошибка при инкременте статистики пользователя {user_id}: {e}")
            return 0

    async def get_user_statistics(self, user_id: int) -> Dict[str, int]:
        """
        Получает всю статистику пользователя.

        Args:
            user_id: ID пользователя.

        Returns:
            Dict[str, int]: Словарь статистики.
        """
        try:
            pattern = f"user_stat:{user_id}:*"
            stat_keys = await self.get_keys_by_pattern(pattern)
            stats = {}
            if not stat_keys:
                return stats
            
            values = await self.redis.mget(stat_keys)
            
            for key, value in zip(stat_keys, values):
                stat_name = key.split(":")[-1]
                if value:
                    stats[stat_name] = int(value)
            return stats
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователя {user_id}: {e}")
            return {}
