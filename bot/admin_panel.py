"""Модуль административных функций"""

import os
import sys
import logging
from typing import Dict, List, Any
from pathlib import Path
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from core.infrastructure_suite import SETTINGS
from core.user_management import user_manager, PermissionType

# Настройка логирования
logger = logging.getLogger(__name__)


def create_admin_keyboard():
    """Создает административную клавиатуру"""
    keyboard = [
        [InlineKeyboardButton(text=" Статистика системы", callback_data="admin:stats")],
        [InlineKeyboardButton(text=" Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton(text=" База данных", callback_data="admin:database")],
        [InlineKeyboardButton(text=" Документы", callback_data="admin:docs")],
        [InlineKeyboardButton(text=" Логи", callback_data="admin:logs")],
        [InlineKeyboardButton(text=" Обновить", callback_data="admin:refresh")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def is_admin(user_id) -> bool:
    """Проверяет, является ли пользователь администратором"""
    logger.info(f" Проверка прав для пользователя {user_id}")
    
    # Проверяем, что user_id является целым числом
    if not isinstance(user_id, int):
        logger.warning(f" user_id не является int: {type(user_id)} = {user_id}")
        return False

    # Проверяем ТОЛЬКО в базе данных (TELEGRAM_ADMIN_IDS fallback убран)
    db_permission_result = check_user_permission_sync(user_id, PermissionType.UPLOAD_DOCUMENTS.value)
    logger.info(f" Результат проверки БД для {user_id}: {db_permission_result}")
    
    logger.info(f" ИТОГОВЫЙ результат для пользователя {user_id}: {db_permission_result}")
    
    return db_permission_result


async def check_user_permission_async(user_id: int, permission: str) -> bool:
    """Асинхронная проверка разрешения пользователя"""
    try:
        return await user_manager.check_permission(user_id, permission)
    except Exception as e:
        logger.error(f" Error checking permission for user {user_id}: {e}")
        # НЕТ FALLBACK - если ошибка в БД, то НЕТ прав
        return False


def check_user_permission_sync(user_id: int, permission: str) -> bool:
    """ИСПРАВЛЕННАЯ синхронная проверка разрешения пользователя через прямой запрос к БД"""
    logger.info(f" check_user_permission_sync для {user_id}, разрешение: {permission}")
    
    try:
        import psycopg2
        from core.infrastructure_suite import SETTINGS
        
        # Прямое подключение к БД без asyncio
        connection = psycopg2.connect(
            host=SETTINGS.POSTGRES_HOST,
            port=SETTINGS.POSTGRES_PORT,
            database=SETTINGS.POSTGRES_DB,
            user=SETTINGS.POSTGRES_USER,
            password=SETTINGS.POSTGRES_PASSWORD if SETTINGS.POSTGRES_PASSWORD else None
        )
        
        with connection.cursor() as cursor:
            # Проверяем права пользователя напрямую в БД
            query = """
            SELECT up.is_granted
            FROM user_permissions up
            JOIN telegram_users tu ON up.telegram_user_id = tu.id
            WHERE tu.telegram_id = %s AND up.permission_type = %s
            """
            
            cursor.execute(query, (user_id, permission))
            row = cursor.fetchone()
            
            if row:
                # ИСПРАВЛЕНИЕ: PostgreSQL возвращает 't'/'f', а не True/False
                result = row[0] == 't' # Правильное преобразование PostgreSQL boolean
                logger.info(f" Результат проверки БД для {user_id}: {result} (raw value: {row[0]})")
            else:
                # Проверяем, существует ли пользователь вообще
                cursor.execute("SELECT 1 FROM telegram_users WHERE telegram_id = %s", (user_id,))
                user_exists = cursor.fetchone()
                
                if not user_exists:
                    logger.info(f" Пользователь {user_id} не найден в БД - очищаем кэш")
                    # Очищаем кэш через Redis напрямую
                    try:
                        import redis
                        redis_client = redis.Redis(
                            host=SETTINGS.REDIS_HOST,
                            port=SETTINGS.REDIS_PORT,
                            db=SETTINGS.REDIS_DB,
                            decode_responses=True
                        )
                        redis_client.delete(f"legalrag:permissions:user:{user_id}")
                        logger.info(f" Очищен кэш для несуществующего пользователя {user_id}")
                    except Exception as cache_error:
                        logger.warning(f" Не удалось очистить кэш для {user_id}: {cache_error}")
                
                result = False
                logger.info(f" Пользователь {user_id} не имеет прав {permission}")
        
        connection.close()
        return result
        
    except Exception as e:
        logger.error(f" Error in sync permission check for user {user_id}: {e}")
        # НЕТ FALLBACK - если ошибка в БД, то НЕТ прав (fail-closed)
        logger.warning(f" Отказываем в правах для {user_id} из-за ошибки БД")
        return False


async def update_user_activity(user_id: int, activity_type: str = "bot_interaction"):
    """Обновление активности пользователя"""
    try:
        user = await user_manager.get_user_by_telegram_id(user_id)
        if user:
            from datetime import datetime
            user.last_activity = datetime.utcnow()
            await user_manager.update_user(user)
    except Exception as e:
        logger.error(f" Error updating user activity for {user_id}: {e}")


def get_logs(lines: int = 100) -> List[str]:
    """Получить последние строки из логов."""
    try:
        log_files = ["telegram_operations.log", "core/logs/app.log", "logs/telegram.log"]

        logs = []
        for log_file in log_files:
            log_path = Path(log_file)
            if log_path.exists():
                try:
                    with open(log_path, "r", encoding="utf-8") as f:
                        file_lines = f.readlines()
                        recent_lines = file_lines[-lines:] if len(file_lines) > lines else file_lines
                        logs.extend([f"[{log_path.name}] {line.strip()}" for line in recent_lines])
                except Exception as e:
                    logs.append(f"[{log_path.name}] Error reading file: {e}")

        if not logs:
            logs.append("No log files found")

        return logs[-lines:]

    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return [f"Error: {str(e)}"]


def format_logs_message(logs: List[str], lines: int = 20) -> str:
    """Форматировать сообщение с логами."""
    try:
        if not logs:
            return " Логи не найдены"

        # Берем только последние строки для отправки
        recent_logs = logs[-lines:] if len(logs) > lines else logs

        message = f" *Последние {len(recent_logs)} записей логов:*\n\n"

        for log in recent_logs:
            # Обрезаем длинные строки
            if len(log) > 80:
                log = log[:77] + "..."
            message += f"`{log}`\n"

        # Проверяем длину сообщения (Telegram ограничение ~4096 символов)
        if len(message) > 4000:
            message = message[:3997] + "..."

        return message

    except Exception as e:
        logger.error(f"Error formatting logs message: {e}")
        return f"Ошибка форматирования логов: {str(e)}"
