#!/usr/bin/env python3
"""
Упрощенная версия admin_panel.py без async проблем
"""

import logging
from typing import List, Optional, Union

from core.infrastructure_suite import SETTINGS

# Настройка логирования
logger = logging.getLogger(__name__)


def is_admin(user_id) -> bool:
    """Проверяет, является ли пользователь администратором"""
    logger.info(f" Простая проверка прав для пользователя {user_id}")
    
    # Проверяем, что user_id является целым числом
    if not isinstance(user_id, int):
        logger.warning(f" user_id не является int: {type(user_id)} = {user_id}")
        return False

    # Проверяем в настройках TELEGRAM_ADMIN_IDS
    env_admin_ids = SETTINGS.TELEGRAM_ADMIN_IDS
    logger.info(f" TELEGRAM_ADMIN_IDS из настроек: {env_admin_ids}")
    
    result = user_id in env_admin_ids
    logger.info(f" Результат проверки для {user_id}: {result}")
    
    return result


def check_user_permission_sync(user_id: int, permission: str) -> bool:
    """Простая синхронная проверка разрешения пользователя"""
    logger.info(f" Простая проверка разрешения {permission} для {user_id}")
    
    # Используем только TELEGRAM_ADMIN_IDS для простоты
    result = user_id in SETTINGS.TELEGRAM_ADMIN_IDS
    logger.info(f" Результат проверки для {user_id}: {result}")
    
    return result


async def check_user_permission_async(user_id: int, permission: str) -> bool:
    """Асинхронная проверка разрешения пользователя"""
    logger.info(f" Async проверка разрешения {permission} для {user_id}")
    
    # Используем только TELEGRAM_ADMIN_IDS для простоты
    result = user_id in SETTINGS.TELEGRAM_ADMIN_IDS
    logger.info(f" Async результат проверки для {user_id}: {result}")
    
    return result