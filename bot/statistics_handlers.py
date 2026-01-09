"""
Модуль для обработки статистических запросов в Telegram боте.
Оптимизирован для работы с PostgreSQL и централизованными сервисами.
"""

import logging
import json
from typing import Dict, Any
from datetime import datetime
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

# Централизованные компоненты
from bot.database_helpers import get_database_statistics, get_user_statistics
from bot.text_formatters import format_statistics_data
from bot.keyboards import create_database_stats_keyboard
from core.data_storage_suite import get_redis_client

logger = logging.getLogger(__name__)


class StatisticsHandler:
    """
    Класс для обработки и предоставления статистических данных.
    Использует централизованные функции для получения данных из PostgreSQL
    и их форматирования.
    """

    def __init__(self, redis_client=None):
        """
        Инициализация обработчика статистики.

        Args:
            redis_client: Клиент Redis для кэширования.
        """
        self.redis_client = redis_client

    async def get_full_statistics(self, user_id: int) -> Dict[str, Any]:
        """
        Получает полную статистику из базы данных и кэширует ее.
        Этот метод является единой точкой для получения всех видов статистики.

        Args:
            user_id: ID пользователя для кэширования (ключ кэша).

        Returns:
            Словарь с полной статистикой.
        """
        cache_key = f"stats:full:{user_id}"
        try:
            # 1. Проверка кэша
            if self.redis_client:
                cached_result = await self.redis_client.get(cache_key)
                if cached_result:
                    logger.info("Полная статистика взята из кэша для user_id: %s", user_id)
                    return json.loads(cached_result)

            # 2. Получение данных из БД
            logger.info("Запрос полной статистики из БД для user_id: %s", user_id)
            db_stats = await get_database_statistics()
            user_stats = await get_user_statistics()

            # 3. Формирование единой структуры данных
            full_stats = {
                "general": {
                    "total_documents": db_stats.get("total_documents", 0),
                    "total_size": db_stats.get("total_size", 0),
                    "avg_size": db_stats.get("avg_size", 0),
                    "total_chunks": db_stats.get("total_chunks", 0),
                    "latest_upload": db_stats.get("latest_upload"),
                },
                "by_type": db_stats.get("by_type", []),
                "by_date": db_stats.get("by_date", []),
                "users": {
                    "total_users": user_stats.get("total_users", 0),
                    "active_today": user_stats.get("active_today", 0),
                    "active_week": user_stats.get("active_week", 0),
                },
                "timestamp": datetime.now().isoformat(),
            }

            # 4. Кэширование результата на 10 минут
            if self.redis_client:
                # Используем ensure_ascii=False для корректной сериализации кириллицы
                await self.redis_client.setex(cache_key, 600, json.dumps(full_stats, ensure_ascii=False))

            return full_stats

        except Exception as e:
            logger.error("Ошибка при получении полной статистики: %s", e, exc_info=True)
            return {"error": str(e)}

    def prepare_statistics_for_formatting(self, stats_type: str, full_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Подготавливает срез данных для передачи в централизованный форматтер.

        Args:
            stats_type: Тип запрашиваемой статистики ('general', 'by_type', 'by_date', 'users').
            full_stats: Полный словарь статистики.

        Returns:
            Словарь, готовый для форматирования.
        """
        if "error" in full_stats:
            return {"error": full_stats["error"], "type": stats_type}

        return {
            "type": stats_type,
            "data": full_stats.get(stats_type, {}),
            "timestamp": full_stats.get("timestamp"),
        }


# Глобальный экземпляр для минимизации создаваемых объектов
statistics_handler = None


def get_statistics_handler() -> StatisticsHandler:
    """
    Фабричная функция для получения синглтона StatisticsHandler.
    Инициализирует обработчик с Redis клиентом.
    """
    global statistics_handler
    if statistics_handler is None:
        redis_client = get_redis_client()
        statistics_handler = StatisticsHandler(redis_client)
    return statistics_handler


async def handle_statistics_request(message: Message | CallbackQuery, stats_type: str):
    """
    Главный обработчик для всех запросов статистики.
    Получает данные, форматирует их и отправляет пользователю.

    Args:
        message: Сообщение или CallbackQuery от пользователя.
        stats_type: Тип запрашиваемой статистики.
    """
    handler = get_statistics_handler()
    user_id = message.from_user.id

    try:
        # 1. Получаем полную статистику (из кэша или БД)
        full_stats = await handler.get_full_statistics(user_id)

        # 2. Выбираем нужный срез данных для форматирования
        stats_to_format = handler.prepare_statistics_for_formatting(stats_type, full_stats)

        # 3. Форматируем данные с помощью централизованного форматтера
        formatted_text = format_statistics_data(stats_to_format)

        # 4. Отправляем результат
        keyboard = create_database_stats_keyboard()
        
        # Проверяем, это сообщение или callback query
        if isinstance(message, Message):
            await message.answer(formatted_text, reply_markup=keyboard, parse_mode="Markdown")
        elif isinstance(message, CallbackQuery):
            await message.message.edit_text(formatted_text, reply_markup=keyboard, parse_mode="Markdown")
            await message.answer()

    except Exception as e:
        logger.error("Критическая ошибка при обработке запроса статистики: %s", e, exc_info=True)
        error_message_text = "❌ Произошла серьезная ошибка при получении статистики."
        if isinstance(message, Message):
            await message.answer(error_message_text)
        elif isinstance(message, CallbackQuery) and message.message:
            await message.message.answer(error_message_text)
