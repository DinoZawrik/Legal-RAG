#!/usr/bin/env python3
"""
Permissions Cache System для LegalRAG
Система кэширования прав пользователей в Redis для быстрого доступа
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
import redis.asyncio as redis

from core.infrastructure_suite import SETTINGS

# Настройка логирования
logger = logging.getLogger(__name__)


class PermissionsCacheManager:
    """Менеджер кэширования прав пользователей в Redis"""
    
    def __init__(self):
        self.redis_client = None
        self.cache_ttl = 3600 # 1 час кэширования
        self.key_prefix = "legalrag:permissions:"
        self.stats_key = "legalrag:cache_stats:permissions"
        
    async def _get_redis_client(self) -> redis.Redis:
        """Получение клиента Redis"""
        if self.redis_client is None:
            try:
                redis_password = getattr(SETTINGS, 'REDIS_PASSWORD', '') or ''
                self.redis_client = redis.Redis(
                    host=SETTINGS.REDIS_HOST,
                    port=SETTINGS.REDIS_PORT,
                    db=SETTINGS.REDIS_DB,
                    password=redis_password or None,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                
                # Проверяем подключение
                await self.redis_client.ping()
                logger.info(" Connected to Redis for permissions cache")
                
            except Exception as e:
                logger.error(f" Failed to connect to Redis: {e}")
                self.redis_client = None
                raise
        
        return self.redis_client
    
    async def close_connection(self):
        """Закрытие соединения с Redis"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info(" Closed Redis connection")
    
    def _get_user_permissions_key(self, telegram_id: int) -> str:
        """Генерация ключа для прав пользователя"""
        return f"{self.key_prefix}user:{telegram_id}"
    
    def _get_upload_users_key(self) -> str:
        """Ключ для списка пользователей с правом загрузки"""
        return f"{self.key_prefix}upload_users"
    
    # ============================================================================
    # Кэширование прав отдельных пользователей
    # ============================================================================
    
    async def cache_user_permissions(self, telegram_id: int, permissions: List[str]) -> bool:
        """Кэширование прав пользователя"""
        try:
            redis_client = await self._get_redis_client()
            
            # Данные для кэширования
            cache_data = {
                'permissions': permissions,
                'cached_at': datetime.utcnow().isoformat(),
                'telegram_id': telegram_id
            }
            
            key = self._get_user_permissions_key(telegram_id)
            
            # Сохраняем в Redis
            await redis_client.setex(
                key, 
                self.cache_ttl, 
                json.dumps(cache_data)
            )
            
            logger.debug(f" Cached permissions for user {telegram_id}: {permissions}")
            return True
            
        except Exception as e:
            logger.error(f" Error caching permissions for user {telegram_id}: {e}")
            return False
    
    async def get_cached_user_permissions(self, telegram_id: int) -> Optional[List[str]]:
        """Получение кэшированных прав пользователя"""
        try:
            redis_client = await self._get_redis_client()
            key = self._get_user_permissions_key(telegram_id)
            
            cached_data = await redis_client.get(key)
            
            if cached_data:
                data = json.loads(cached_data)
                permissions = data.get('permissions', [])
                
                # Обновляем статистику попаданий в кэш
                await self._update_cache_stats('hit')
                
                logger.debug(f" Cache hit for user {telegram_id}: {permissions}")
                return permissions
            else:
                # Промах кэша
                await self._update_cache_stats('miss')
                logger.debug(f" Cache miss for user {telegram_id}")
                return None
                
        except Exception as e:
            logger.error(f" Error getting cached permissions for user {telegram_id}: {e}")
            return None
    
    async def check_cached_permission(self, telegram_id: int, permission: str) -> Optional[bool]:
        """Проверка конкретного разрешения из кэша"""
        try:
            permissions = await self.get_cached_user_permissions(telegram_id)
            
            if permissions is not None:
                return permission in permissions
            
            return None
            
        except Exception as e:
            logger.error(f" Error checking cached permission {permission} for user {telegram_id}: {e}")
            return None
    
    async def invalidate_user_permissions(self, telegram_id: int) -> bool:
        """Инвалидация кэша прав пользователя"""
        try:
            redis_client = await self._get_redis_client()
            key = self._get_user_permissions_key(telegram_id)
            
            deleted = await redis_client.delete(key)
            
            if deleted:
                logger.info(f" Invalidated permissions cache for user {telegram_id}")
            
            return deleted > 0
            
        except Exception as e:
            logger.error(f" Error invalidating permissions cache for user {telegram_id}: {e}")
            return False
    
    # ============================================================================
    # Кэширование списка пользователей с правом загрузки
    # ============================================================================
    
    async def cache_upload_users(self, user_ids: List[int]) -> bool:
        """Кэширование списка пользователей с правом загрузки"""
        try:
            redis_client = await self._get_redis_client()
            
            cache_data = {
                'user_ids': user_ids,
                'cached_at': datetime.utcnow().isoformat(),
                'count': len(user_ids)
            }
            
            key = self._get_upload_users_key()
            
            await redis_client.setex(
                key,
                self.cache_ttl,
                json.dumps(cache_data)
            )
            
            logger.info(f" Cached {len(user_ids)} upload users")
            return True
            
        except Exception as e:
            logger.error(f" Error caching upload users: {e}")
            return False
    
    async def get_cached_upload_users(self) -> Optional[List[int]]:
        """Получение кэшированного списка пользователей с правом загрузки"""
        try:
            redis_client = await self._get_redis_client()
            key = self._get_upload_users_key()
            
            cached_data = await redis_client.get(key)
            
            if cached_data:
                data = json.loads(cached_data)
                user_ids = data.get('user_ids', [])
                
                await self._update_cache_stats('hit')
                logger.debug(f" Cache hit for upload users: {len(user_ids)} users")
                return user_ids
            else:
                await self._update_cache_stats('miss')
                logger.debug(" Cache miss for upload users")
                return None
                
        except Exception as e:
            logger.error(f" Error getting cached upload users: {e}")
            return None
    
    async def invalidate_upload_users_cache(self) -> bool:
        """Инвалидация кэша списка пользователей с правом загрузки"""
        try:
            redis_client = await self._get_redis_client()
            key = self._get_upload_users_key()
            
            deleted = await redis_client.delete(key)
            
            if deleted:
                logger.info(" Invalidated upload users cache")
            
            return deleted > 0
            
        except Exception as e:
            logger.error(f" Error invalidating upload users cache: {e}")
            return False
    
    # ============================================================================
    # Массовая инвалидация и обновление
    # ============================================================================
    
    async def invalidate_all_permissions_cache(self) -> bool:
        """Полная очистка кэша прав"""
        try:
            redis_client = await self._get_redis_client()
            
            # Находим все ключи с префиксом permissions
            pattern = f"{self.key_prefix}*"
            keys = []
            
            async for key in redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await redis_client.delete(*keys)
                logger.info(f" Invalidated {deleted} permission cache entries")
                return True
            else:
                logger.info(" No permission cache entries to invalidate")
                return True
                
        except Exception as e:
            logger.error(f" Error invalidating all permissions cache: {e}")
            return False
    
    async def refresh_user_permissions_cache(self, telegram_id: int, from_db_func) -> Optional[List[str]]:
        """Обновление кэша прав пользователя из БД"""
        try:
            # Инвалидируем старый кэш
            await self.invalidate_user_permissions(telegram_id)
            
            # Получаем актуальные данные из БД
            user = await from_db_func(telegram_id)
            
            if user and user.permissions:
                # Кэшируем новые данные
                await self.cache_user_permissions(telegram_id, user.permissions)
                return user.permissions
            
            return []
            
        except Exception as e:
            logger.error(f" Error refreshing permissions cache for user {telegram_id}: {e}")
            return None
    
    # ============================================================================
    # Статистика кэширования
    # ============================================================================
    
    async def _update_cache_stats(self, event_type: str):
        """Обновление статистики кэша"""
        try:
            redis_client = await self._get_redis_client()
            
            # Увеличиваем счетчик для типа события
            await redis_client.hincrby(self.stats_key, event_type, 1)
            
            # Устанавливаем TTL для статистики (24 часа)
            await redis_client.expire(self.stats_key, 86400)
            
        except Exception as e:
            logger.error(f" Error updating cache stats: {e}")
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Получение статистики кэширования"""
        try:
            redis_client = await self._get_redis_client()
            
            stats = await redis_client.hgetall(self.stats_key)
            
            hits = int(stats.get('hit', 0))
            misses = int(stats.get('miss', 0))
            total = hits + misses
            
            hit_rate = (hits / total * 100) if total > 0 else 0
            
            return {
                'hits': hits,
                'misses': misses,
                'total_requests': total,
                'hit_rate_percent': round(hit_rate, 2),
                'cache_status': 'healthy' if hit_rate > 60 else 'needs_optimization'
            }
            
        except Exception as e:
            logger.error(f" Error getting cache statistics: {e}")
            return {
                'hits': 0,
                'misses': 0,
                'total_requests': 0,
                'hit_rate_percent': 0,
                'cache_status': 'error',
                'error': str(e)
            }
    
    # ============================================================================
    # Периодическое обслуживание кэша
    # ============================================================================
    
    async def cleanup_expired_cache(self):
        """Очистка устаревших записей кэша"""
        try:
            redis_client = await self._get_redis_client()
            
            # Redis автоматически удаляет записи с истекшим TTL
            # Здесь можем добавить дополнительную логику при необходимости
            
            logger.info(" Cache cleanup completed")
            
        except Exception as e:
            logger.error(f" Error during cache cleanup: {e}")
    
    async def warm_up_cache(self, user_manager):
        """Предварительное наполнение кэша актуальными данными"""
        try:
            logger.info(" Starting cache warm-up...")
            
            # Получаем всех пользователей с правами загрузки
            upload_users = await user_manager.get_users_with_upload_permission()
            
            if upload_users:
                # Кэшируем список пользователей с правом загрузки
                await self.cache_upload_users(upload_users)
                
                # Предварительно кэшируем права для активных пользователей
                for user_id in upload_users[:50]: # Ограничиваем до 50 пользователей
                    user = await user_manager.get_user_by_telegram_id(user_id)
                    if user and user.permissions:
                        await self.cache_user_permissions(user_id, user.permissions)
            
            logger.info(f" Cache warm-up completed for {len(upload_users)} users")
            
        except Exception as e:
            logger.error(f" Error during cache warm-up: {e}")


# Глобальный экземпляр менеджера кэширования
permissions_cache = PermissionsCacheManager()