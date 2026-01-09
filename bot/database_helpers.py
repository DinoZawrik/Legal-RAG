"""
Вспомогательные функции для работы с базой данных в контексте запросов прав доступа.

Этот модуль содержит функции для создания и обработки запросов на получение прав доступа.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
import asyncpg
from core.infrastructure_suite import SETTINGS

logger = logging.getLogger(__name__)


class DatabaseHelper:
    """Вспомогательный класс для работы с базой данных"""
    
    def __init__(self):
        """Инициализация помощника базы данных"""
        # Простое извлечение пароля
        password = SETTINGS.POSTGRES_PASSWORD if SETTINGS.POSTGRES_PASSWORD else None
        
        # Собираем параметры подключения из настроек
        self.db_config = {
            'host': SETTINGS.POSTGRES_HOST,
            'port': SETTINGS.POSTGRES_PORT,
            'database': SETTINGS.POSTGRES_DB,
            'user': SETTINGS.POSTGRES_USER,
            'password': password
        }
    
    async def get_connection(self) -> asyncpg.Connection:
        """Получение соединения с базой данных"""
        return await asyncpg.connect(**self.db_config)
    
    async def create_permission_request(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        requested_permission: str = 'upload_documents',
        request_message: Optional[str] = None
    ) -> Optional[int]:
        """Создание запроса на получение прав доступа"""
        
        try:
            conn = await self.get_connection()
            try:
                # Вызываем функцию PostgreSQL для создания запроса
                result = await conn.fetchval(
                    """
                    SELECT create_permission_request(
                        $1, $2, $3, $4, $5, $6
                    )
                    """,
                    telegram_id,
                    username,
                    first_name,
                    last_name,
                    requested_permission,
                    request_message
                )
                
                logger.info(f"Создан запрос на права доступа ID: {result} для пользователя {telegram_id}")
                return result
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Ошибка при создании запроса на права доступа: {e}")
            return None
    
    async def process_permission_request(
        self,
        request_id: int,
        action: str,
        admin_comment: Optional[str] = None,
        processed_by: str = 'admin'
    ) -> bool:
        """Обработка запроса (одобрение/отклонение)"""
        
        try:
            conn = await self.get_connection()
            try:
                # Вызываем функцию PostgreSQL для обработки запроса
                result = await conn.fetchval(
                    """
                    SELECT process_permission_request(
                        $1, $2, $3, $4
                    )
                    """,
                    request_id,
                    action,
                    admin_comment,
                    processed_by
                )
                
                success = bool(result)
                logger.info(f"Запрос ID: {request_id} обработан: {action}, успех: {success}")
                return success
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса ID: {request_id}: {e}")
            return False
    
    async def get_user_active_requests(self, telegram_id: int) -> list:
        """Получение активных запросов конкретного пользователя"""
        
        try:
            conn = await self.get_connection()
            try:
                query = """
                    SELECT * FROM v_permission_requests_display 
                    WHERE telegram_id = $1 AND status = 'pending' 
                    ORDER BY requested_at DESC
                """
                result = await conn.fetch(query, telegram_id)
                
                return [dict(row) for row in result]
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Ошибка при получении активных запросов пользователя {telegram_id}: {e}")
            return []
    
    async def get_permission_requests(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """Получение списка запросов на права доступа"""
        
        try:
            conn = await self.get_connection()
            try:
                # Формируем запрос в зависимости от статуса
                if status:
                    query = """
                        SELECT * FROM v_permission_requests_display 
                        WHERE status = $1 
                        ORDER BY requested_at DESC 
                        LIMIT $2 OFFSET $3
                    """
                    result = await conn.fetch(query, status, limit, offset)
                else:
                    query = """
                        SELECT * FROM v_permission_requests_display 
                        ORDER BY requested_at DESC 
                        LIMIT $1 OFFSET $2
                    """
                    result = await conn.fetch(query, limit, offset)
                
                return [dict(row) for row in result]
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Ошибка при получении запросов на права: {e}")
            return []
    
    async def get_permission_request(self, request_id: int) -> Optional[Dict]:
        """Получение конкретного запроса на права доступа"""
        
        try:
            conn = await self.get_connection()
            try:
                query = """
                    SELECT * FROM v_permission_requests_display 
                    WHERE id = $1
                """
                row = await conn.fetchrow(query, request_id)
                
                return dict(row) if row else None
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Ошибка при получении запроса ID: {request_id}: {e}")
            return None
    
    async def delete_permission_request(self, request_id: int) -> bool:
        """Удаление запроса на права доступа"""
        
        try:
            conn = await self.get_connection()
            try:
                # Удаляем запрос
                result = await conn.execute(
                    "DELETE FROM permission_requests WHERE id = $1",
                    request_id
                )
                
                success = "DELETE 1" in result
                logger.info(f"Запрос ID: {request_id} удален, успех: {success}")
                return success
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Ошибка при удалении запроса ID: {request_id}: {e}")
            return False
    
    async def batch_process_requests(
        self,
        request_ids: list,
        action: str,
        admin_comment: Optional[str] = None,
        processed_by: str = 'admin'
    ) -> Dict[str, Any]:
        """Массовая обработка запросов"""
        
        try:
            conn = await self.get_connection()
            try:
                # Начинаем транзакцию
                async with conn.transaction():
                    processed_count = 0
                    failed_ids = []
                    
                    for request_id in request_ids:
                        try:
                            success = await conn.fetchval(
                                """
                                SELECT process_permission_request(
                                    $1, $2, $3, $4
                                )
                                """,
                                request_id,
                                action,
                                admin_comment,
                                processed_by
                            )
                            
                            if success:
                                processed_count += 1
                            else:
                                failed_ids.append(request_id)
                                
                        except Exception as e:
                            logger.error(f"Ошибка при обработке запроса ID: {request_id}: {e}")
                            failed_ids.append(request_id)
                    
                    return {
                        'success': len(failed_ids) == 0,
                        'processed_count': processed_count,
                        'failed_count': len(failed_ids),
                        'failed_ids': failed_ids,
                        'message': f"Обработано {processed_count} запросов, {len(failed_ids)} не удалось"
                    }
            finally:
                await conn.close()
                    
        except Exception as e:
            logger.error(f"Ошибка при массовой обработке запросов: {e}")
            return {
                'success': False,
                'processed_count': 0,
                'failed_count': len(request_ids),
                'failed_ids': request_ids,
                'message': f"Ошибка при массовой обработке: {str(e)}"
            }
    
    async def batch_delete_requests(self, request_ids: list) -> Dict[str, Any]:
        """Массовое удаление запросов"""
        
        try:
            conn = await self.get_connection()
            try:
                # Удаляем запросы
                result = await conn.execute(
                    """
                    DELETE FROM permission_requests 
                    WHERE id = ANY($1)
                    """,
                    request_ids
                )
                
                deleted_count = int(result.split()[-1]) if result else 0
                
                return {
                    'success': True,
                    'deleted_count': deleted_count,
                    'message': f"Удалено {deleted_count} запросов"
                }
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Ошибка при массовом удалении запросов: {e}")
            return {
                'success': False,
                'deleted_count': 0,
                'message': f"Ошибка при массовом удалении: {str(e)}"
            }


# Глобальный экземпляр помощника базы данных
_db_helper = None


async def get_db_helper() -> DatabaseHelper:
    """Получение глобального экземпляра помощника базы данных"""
    global _db_helper
    if _db_helper is None:
        _db_helper = DatabaseHelper()
    return _db_helper


async def create_permission_request(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    requested_permission: str = 'upload_documents',
    request_message: Optional[str] = None
) -> Optional[int]:
    """Создание запроса на получение прав доступа (синхронная обертка)"""
    
    try:
        db_helper = await get_db_helper()
        return await db_helper.create_permission_request(
            telegram_id, username, first_name, last_name,
            requested_permission, request_message
        )
    except Exception as e:
        logger.error(f"Ошибка при создании запроса на права: {e}")
        return None


async def get_user_active_requests(telegram_id: int) -> list:
    """Получение активных запросов пользователя"""
    
    try:
        db_helper = await get_db_helper()
        return await db_helper.get_user_active_requests(telegram_id)
    except Exception as e:
        logger.error(f"Ошибка при получении активных запросов пользователя {telegram_id}: {e}")
        return []
