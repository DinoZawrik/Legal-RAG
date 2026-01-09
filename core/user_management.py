#!/usr/bin/env python3
"""
User Management System для LegalRAG
Система управления пользователями Telegram и их правами
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import asyncpg

from core.infrastructure_suite import SETTINGS
from core.permissions_cache import permissions_cache

# Настройка логирования
logger = logging.getLogger(__name__)


class PermissionType(Enum):
    """Типы разрешений пользователей"""
    UPLOAD_DOCUMENTS = "upload_documents"
    ADMIN_ACCESS = "admin_access"
    VIEW_LOGS = "view_logs"
    MANAGE_USERS = "manage_users"
    VIEW_STATISTICS = "view_statistics"


class UserStatus(Enum):
    """Статусы пользователей"""
    ACTIVE = "active"
    BLOCKED = "blocked"
    INACTIVE = "inactive"


@dataclass
class TelegramUser:
    """Модель пользователя Telegram"""
    id: Optional[int] = None
    telegram_id: int = 0
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: UserStatus = UserStatus.ACTIVE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    added_by: Optional[str] = None
    comment: Optional[str] = None
    permissions: List[str] = None
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для API"""
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'status': self.status.value if isinstance(self.status, UserStatus) else self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'added_by': self.added_by,
            'comment': self.comment,
            'permissions': self.permissions
        }


@dataclass
class UserPermission:
    """Модель разрешения пользователя"""
    id: Optional[int] = None
    telegram_user_id: int = 0
    permission_type: str = ""
    is_granted: bool = True
    granted_at: Optional[datetime] = None
    granted_by: Optional[str] = None
    expires_at: Optional[datetime] = None


class UserManager:
    """Менеджер для работы с пользователями и их правами"""
    
    def __init__(self):
        self.db_config = {
            'host': SETTINGS.POSTGRES_HOST,
            'port': SETTINGS.POSTGRES_PORT,
            'database': SETTINGS.POSTGRES_DB,
            'user': SETTINGS.POSTGRES_USER,
            'password': SETTINGS.POSTGRES_PASSWORD if SETTINGS.POSTGRES_PASSWORD else None
        }
        self._connection_pool = None
    
    async def _get_connection_pool(self) -> asyncpg.Pool:
        """Получение пула подключений к базе данных"""
        if self._connection_pool is None or self._connection_pool.is_closing():
            try:
                self._connection_pool = await asyncpg.create_pool(
                    **self.db_config,
                    min_size=1,
                    max_size=10,
                    command_timeout=60
                )
                logger.info("✅ Created database connection pool")
            except Exception as e:
                logger.error(f"❌ Failed to create connection pool: {e}")
                raise
        
        return self._connection_pool
    
    async def close_connection_pool(self):
        """Закрытие пула подключений"""
        if self._connection_pool and not self._connection_pool.is_closing():
            await self._connection_pool.close()
            logger.info("🔒 Closed database connection pool")
    
    # ============================================================================
    # CRUD операции для пользователей
    # ============================================================================
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[TelegramUser]:
        """Получение пользователя по Telegram ID"""
        pool = await self._get_connection_pool()
        
        async with pool.acquire() as conn:
            try:
                # Получаем пользователя с разрешениями
                query = """
                SELECT 
                    tu.*,
                    STRING_AGG(
                        CASE WHEN up.is_granted THEN up.permission_type ELSE NULL END, 
                        ','
                    ) as permissions
                FROM telegram_users tu
                LEFT JOIN user_permissions up ON tu.id = up.telegram_user_id
                WHERE tu.telegram_id = $1
                GROUP BY tu.id
                """
                
                row = await conn.fetchrow(query, telegram_id)
                
                if not row:
                    return None
                
                permissions = []
                if row['permissions']:
                    permissions = row['permissions'].split(',')
                
                return TelegramUser(
                    id=row['id'],
                    telegram_id=row['telegram_id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    status=UserStatus(row['status']),
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    last_activity=row['last_activity'],
                    added_by=row['added_by'],
                    comment=row['comment'],
                    permissions=permissions
                )
                
            except Exception as e:
                logger.error(f"❌ Error getting user by telegram_id {telegram_id}: {e}")
                return None
    
    async def create_user(self, user: TelegramUser, granted_by: str = "system") -> Optional[TelegramUser]:
        """Создание нового пользователя"""
        pool = await self._get_connection_pool()
        
        async with pool.acquire() as conn:
            try:
                async with conn.transaction():
                    # Создаем пользователя
                    insert_user_query = """
                    INSERT INTO telegram_users (telegram_id, username, first_name, last_name, status, added_by, comment)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id, created_at, updated_at
                    """
                    
                    user_row = await conn.fetchrow(
                        insert_user_query,
                        user.telegram_id,
                        user.username,
                        user.first_name,
                        user.last_name,
                        user.status.value if isinstance(user.status, UserStatus) else user.status,
                        granted_by,
                        user.comment
                    )
                    
                    user.id = user_row['id']
                    user.created_at = user_row['created_at']
                    user.updated_at = user_row['updated_at']
                    
                    # Добавляем разрешения
                    if user.permissions:
                        for permission in user.permissions:
                            await self._grant_permission(
                                conn, user.id, permission, granted_by
                            )
                    
                    logger.info(f"✅ Created user {user.telegram_id} with {len(user.permissions)} permissions")
                    return user
                    
            except asyncpg.UniqueViolationError:
                logger.warning(f"⚠️ User with telegram_id {user.telegram_id} already exists")
                return None
            except Exception as e:
                logger.error(f"❌ Error creating user: {e}")
                return None
    
    async def update_user(self, user: TelegramUser) -> bool:
        """Обновление пользователя"""
        pool = await self._get_connection_pool()
        
        async with pool.acquire() as conn:
            try:
                query = """
                UPDATE telegram_users 
                SET username = $2, first_name = $3, last_name = $4, 
                    status = $5, comment = $6, last_activity = $7
                WHERE telegram_id = $1
                """
                
                result = await conn.execute(
                    query,
                    user.telegram_id,
                    user.username,
                    user.first_name,
                    user.last_name,
                    user.status.value if isinstance(user.status, UserStatus) else user.status,
                    user.comment,
                    user.last_activity or datetime.utcnow()
                )
                
                logger.info(f"✅ Updated user {user.telegram_id}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error updating user {user.telegram_id}: {e}")
                return False
    
    async def delete_user(self, telegram_id: int) -> bool:
        """Удаление пользователя"""
        pool = await self._get_connection_pool()
        
        async with pool.acquire() as conn:
            try:
                # CASCADE автоматически удалит разрешения
                result = await conn.execute(
                    "DELETE FROM telegram_users WHERE telegram_id = $1",
                    telegram_id
                )
                
                logger.info(f"✅ Deleted user {telegram_id}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error deleting user {telegram_id}: {e}")
                return False
    
    async def get_all_users(self, limit: int = 100, offset: int = 0) -> List[TelegramUser]:
        """Получение всех пользователей с пагинацией"""
        pool = await self._get_connection_pool()
        
        async with pool.acquire() as conn:
            try:
                query = """
                SELECT 
                    tu.*,
                    STRING_AGG(
                        CASE WHEN up.is_granted THEN up.permission_type ELSE NULL END, 
                        ','
                    ) as permissions
                FROM telegram_users tu
                LEFT JOIN user_permissions up ON tu.id = up.telegram_user_id
                GROUP BY tu.id
                ORDER BY tu.created_at DESC
                LIMIT $1 OFFSET $2
                """
                
                rows = await conn.fetch(query, limit, offset)
                
                users = []
                for row in rows:
                    permissions = []
                    if row['permissions']:
                        permissions = row['permissions'].split(',')
                    
                    user = TelegramUser(
                        id=row['id'],
                        telegram_id=row['telegram_id'],
                        username=row['username'],
                        first_name=row['first_name'],
                        last_name=row['last_name'],
                        status=UserStatus(row['status']),
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        last_activity=row['last_activity'],
                        added_by=row['added_by'],
                        comment=row['comment'],
                        permissions=permissions
                    )
                    users.append(user)
                
                logger.info(f"✅ Retrieved {len(users)} users")
                return users
                
            except Exception as e:
                logger.error(f"❌ Error getting all users: {e}")
                return []
    
    # ============================================================================
    # Управление разрешениями
    # ============================================================================
    
    async def _grant_permission(self, conn: asyncpg.Connection, user_id: int, 
                               permission_type: str, granted_by: str):
        """Внутренний метод для выдачи разрешения"""
        query = """
        INSERT INTO user_permissions (telegram_user_id, permission_type, granted_by)
        VALUES ($1, $2, $3)
        ON CONFLICT (telegram_user_id, permission_type) 
        DO UPDATE SET is_granted = true, granted_at = CURRENT_TIMESTAMP, granted_by = EXCLUDED.granted_by
        """
        
        await conn.execute(query, user_id, permission_type, granted_by)
    
    async def grant_permission(self, telegram_id: int, permission_type: str, granted_by: str = "admin") -> bool:
        """Выдача разрешения пользователю"""
        pool = await self._get_connection_pool()
        
        async with pool.acquire() as conn:
            try:
                # Получаем ID пользователя
                user_id_row = await conn.fetchrow(
                    "SELECT id FROM telegram_users WHERE telegram_id = $1", 
                    telegram_id
                )
                
                if not user_id_row:
                    logger.warning(f"⚠️ User {telegram_id} not found for permission grant")
                    return False
                
                await self._grant_permission(conn, user_id_row['id'], permission_type, granted_by)
                
                # Инвалидируем кэш пользователя
                await permissions_cache.invalidate_user_permissions(telegram_id)
                
                # Если это право загрузки, инвалидируем кэш списка пользователей
                if permission_type == PermissionType.UPLOAD_DOCUMENTS.value:
                    await permissions_cache.invalidate_upload_users_cache()
                
                logger.info(f"✅ Granted permission {permission_type} to user {telegram_id}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error granting permission {permission_type} to user {telegram_id}: {e}")
                return False
    
    async def revoke_permission(self, telegram_id: int, permission_type: str) -> bool:
        """Отзыв разрешения у пользователя"""
        pool = await self._get_connection_pool()
        
        async with pool.acquire() as conn:
            try:
                query = """
                UPDATE user_permissions 
                SET is_granted = false 
                WHERE telegram_user_id = (
                    SELECT id FROM telegram_users WHERE telegram_id = $1
                ) AND permission_type = $2
                """
                
                result = await conn.execute(query, telegram_id, permission_type)
                
                # Инвалидируем кэш пользователя
                await permissions_cache.invalidate_user_permissions(telegram_id)
                
                # Если это право загрузки, инвалидируем кэш списка пользователей
                if permission_type == PermissionType.UPLOAD_DOCUMENTS.value:
                    await permissions_cache.invalidate_upload_users_cache()
                
                logger.info(f"✅ Revoked permission {permission_type} from user {telegram_id}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error revoking permission {permission_type} from user {telegram_id}: {e}")
                return False
    
    async def check_permission(self, telegram_id: int, permission_type: str) -> bool:
        """Проверка наличия разрешения у пользователя с кэшированием"""
        try:
            # ИСПРАВЛЕНИЕ: Сначала проверяем БД, потом кэш
            pool = await self._get_connection_pool()
            
            async with pool.acquire() as conn:
                query = """
                SELECT up.is_granted
                FROM user_permissions up
                JOIN telegram_users tu ON up.telegram_user_id = tu.id
                WHERE tu.telegram_id = $1 AND up.permission_type = $2
                """
                
                row = await conn.fetchrow(query, telegram_id, permission_type)
                result = row['is_granted'] if row else False
                
                # Если пользователь не найден в БД, принудительно очищаем кэш
                if not result:
                    # Проверяем, есть ли пользователь в БД вообще
                    user_exists_query = "SELECT 1 FROM telegram_users WHERE telegram_id = $1"
                    user_exists = await conn.fetchval(user_exists_query, telegram_id)
                    
                    if not user_exists:
                        # Пользователя нет в БД - очищаем его кэш
                        await permissions_cache.invalidate_user_permissions(telegram_id)
                        logger.info(f"🧹 Cleared cache for non-existent user {telegram_id}")
                
                # Обновляем кэш актуальными данными из БД
                user = await self.get_user_by_telegram_id(telegram_id)
                if user and user.permissions:
                    await permissions_cache.cache_user_permissions(telegram_id, user.permissions)
                elif not user:
                    # Если пользователя нет, кэшируем пустые права
                    await permissions_cache.cache_user_permissions(telegram_id, [])
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Error checking permission {permission_type} for user {telegram_id}: {e}")
            return False
    
    # ============================================================================
    # Интеграция с существующей системой
    # ============================================================================
    
    async def get_users_with_upload_permission(self) -> List[int]:
        """Получение списка Telegram ID пользователей с правом загрузки с кэшированием"""
        try:
            # Сначала проверяем кэш
            cached_users = await permissions_cache.get_cached_upload_users()
            
            if cached_users is not None:
                return cached_users
            
            # Если в кэше нет, обращаемся к БД
            pool = await self._get_connection_pool()
            
            async with pool.acquire() as conn:
                query = """
                SELECT tu.telegram_id
                FROM telegram_users tu
                JOIN user_permissions up ON tu.id = up.telegram_user_id
                WHERE up.permission_type = $1 AND up.is_granted = true AND tu.status = 'active'
                """
                
                rows = await conn.fetch(query, PermissionType.UPLOAD_DOCUMENTS.value)
                telegram_ids = [row['telegram_id'] for row in rows]
                
                # Кэшируем результат
                await permissions_cache.cache_upload_users(telegram_ids)
                
                logger.info(f"✅ Found {len(telegram_ids)} users with upload permission")
                return telegram_ids
                
        except Exception as e:
            logger.error(f"❌ Error getting users with upload permission: {e}")
            return []
    
    async def sync_with_environment_variable(self) -> bool:
        """Синхронизация с переменной окружения TELEGRAM_ADMIN_IDS"""
        try:
            # Получаем ID из переменной окружения
            admin_ids_from_env = SETTINGS.TELEGRAM_ADMIN_IDS
            
            # Получаем ID из базы данных
            admin_ids_from_db = await self.get_users_with_upload_permission()
            
            # Добавляем отсутствующих пользователей из .env в БД
            for telegram_id in admin_ids_from_env:
                if telegram_id not in admin_ids_from_db:
                    user = TelegramUser(
                        telegram_id=telegram_id,
                        username=f"env_user_{telegram_id}",
                        first_name="Environment User",
                        status=UserStatus.ACTIVE,
                        comment="Migrated from TELEGRAM_ADMIN_IDS environment variable",
                        permissions=[PermissionType.UPLOAD_DOCUMENTS.value]
                    )
                    
                    await self.create_user(user, "environment_sync")
            
            logger.info("✅ Synchronized users with environment variable")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error syncing with environment variable: {e}")
            return False
    
    # ============================================================================
    # Статистика и аналитика
    # ============================================================================
    
    async def get_user_statistics(self) -> Dict[str, Any]:
        """Получение статистики пользователей"""
        pool = await self._get_connection_pool()
        
        async with pool.acquire() as conn:
            try:
                # Общая статистика
                total_users = await conn.fetchval("SELECT COUNT(*) FROM telegram_users")
                active_users = await conn.fetchval(
                    "SELECT COUNT(*) FROM telegram_users WHERE status = 'active'"
                )
                
                # Пользователи за последний месяц
                new_users_month = await conn.fetchval(
                    "SELECT COUNT(*) FROM telegram_users WHERE created_at >= $1",
                    datetime.utcnow() - timedelta(days=30)
                )
                
                # Активность сегодня
                daily_active = await conn.fetchval(
                    "SELECT COUNT(*) FROM telegram_users WHERE last_activity >= $1",
                    datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                )
                
                # Распределение по разрешениям
                permissions_query = """
                SELECT up.permission_type, COUNT(*) as count
                FROM user_permissions up
                WHERE up.is_granted = true
                GROUP BY up.permission_type
                """
                permission_rows = await conn.fetch(permissions_query)
                roles_distribution = {row['permission_type']: row['count'] for row in permission_rows}
                
                return {
                    'total_users': total_users,
                    'active_users': active_users,
                    'new_users_month': new_users_month,
                    'daily_active': daily_active,
                    'roles_distribution': roles_distribution,
                    'daily_activity': {},  # Можно расширить при необходимости
                    'top_active_users': []  # Можно расширить при необходимости
                }
                
            except Exception as e:
                logger.error(f"❌ Error getting user statistics: {e}")
                return {}


# Глобальный экземпляр менеджера пользователей
user_manager = UserManager()