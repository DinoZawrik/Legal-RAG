#!/usr/bin/env python3
"""
🤖 Telegram Bot Core
Основной модуль телеграм-бота с интеграцией всех обработчиков.

Включает функциональность:
- Основной класс TelegramBot
- Инициализация и конфигурация
- Регистрация обработчиков
- Запуск polling
"""

import asyncio
import logging
import os
import sys

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher, F
from aiogram.types import BotCommand
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.redis import RedisStorage, Redis
import redis.asyncio as redis_async

from core.infrastructure_suite import SETTINGS, initialize_core_system
from bot.enhanced_legal_bot_adapter import EnhancedLegalBotAdapter
from core.processing_pipeline import UnifiedDocumentProcessor, DocumentType
from bot.user_history import UserHistory
from bot.archive_processor import ArchiveProcessor
from bot.permission_notifications import PermissionNotifications

# Импорт модульных обработчиков
from bot.message_handlers import MessageHandlers
from bot.command_handlers import CommandHandlers
from bot.document_handlers import DocumentHandlers
from bot.user_management import UserManagement
from bot.states import Form

# Настройка логирования
logger = logging.getLogger(__name__)
telegram_logger = logging.getLogger("telegram_operations")

# Глобальная переменная для доступа к экземпляру бота
_global_bot_instance = None


def get_bot_instance():
    """Получение глобального экземпляра бота"""
    return _global_bot_instance


class TelegramBot:
    """Основной класс телеграм-бота с модульной архитектурой."""

    def __init__(self, token: str):
        """Инициализация бота."""
        self.redis = Redis(host=SETTINGS.REDIS_HOST, port=SETTINGS.REDIS_PORT, db=SETTINGS.REDIS_DB)
        self.async_redis = None  # Будет инициализирован в start_polling
        self.storage = RedisStorage(self.redis)
        self.bot = Bot(token=token)
        self.dp = Dispatcher(bot=self.bot, storage=self.storage)
        self.processing_pipeline = UnifiedDocumentProcessor()
        self.archive_processor = ArchiveProcessor()
        self.processing_users = set()
        self.user_history = None  # Будет инициализировано позже
        self.api_gateway_url = os.getenv("API_GATEWAY_URL", "http://localhost:8080")
        self.notification_service = PermissionNotifications(self.bot)

        # Инициализация модульных обработчиков
        self.message_handlers = MessageHandlers(self)
        self.command_handlers = CommandHandlers(self)
        self.document_handlers = DocumentHandlers(self)
        self.user_management = UserManagement(self)

        # Регистрация обработчиков
        self._register_handlers()

    async def setup_bot_commands(self):
        """Настройка команд бота для меню."""
        commands = [
            BotCommand(command="start", description="🚀 Начать работу"),
            BotCommand(command="help", description="❓ Помощь"),
            BotCommand(command="upload", description="📄 Загрузить документ"),
            BotCommand(command="clear", description="🗑️ Очистить все сообщения (кроме документов)"),
            BotCommand(command="request_access", description="🔑 Запросить права доступа"),
        ]
        await self.bot.set_my_commands(commands)

    def _register_handlers(self):
        """Регистрация всех обработчиков команд и сообщений."""
        logger.info("Регистрация обработчиков...")

        # Команды
        self.dp.message.register(self.command_handlers.start_command, CommandStart())
        self.dp.message.register(self.command_handlers.help_command, Command("help"))
        self.dp.message.register(self.command_handlers.upload_command, Command("upload"))
        self.dp.message.register(self.command_handlers.request_access_command, Command("request_access"))
        self.dp.message.register(self.command_handlers.clear_command, Command("clear"))

        # Обработка документов
        self.dp.message.register(self.document_handlers.handle_document_upload, F.document)

        # Обработка текстовых сообщений (должен быть последним)
        self.dp.message.register(self.message_handlers.handle_text_message)

        # Обработчики нажатий на инлайн-кнопки
        self.dp.callback_query.register(self.user_management.handle_clear_confirmation, F.data == "doc_manage:confirm_clear")
        self.dp.callback_query.register(self.user_management.handle_cancel_clear, F.data == "doc_manage:cancel_clear")
        self.dp.callback_query.register(self.document_handlers.handle_document_type_selection, Form.selecting_document_type)

        logger.info("Обработчики успешно зарегистрированы.")

    async def start_polling(self):
        """Запуск бота в режиме long polling с полной инициализацией."""
        global _global_bot_instance
        _global_bot_instance = self

        try:
            logger.info("🚀 Запуск Telegram бота...")

            # Инициализация основной системы
            logger.info("🔧 Инициализация основной системы...")
            await initialize_core_system()

            # Инициализация async Redis клиента
            logger.info("🔧 Подключение к Redis...")
            self.async_redis = redis_async.from_url(
                f"redis://{SETTINGS.REDIS_HOST}:{SETTINGS.REDIS_PORT}/{SETTINGS.REDIS_DB}",
                decode_responses=True
            )

            # Проверка подключения к Redis
            await self.async_redis.ping()
            logger.info("✅ Redis подключение установлено")

            # Инициализация истории пользователей
            logger.info("🔧 Инициализация истории пользователей...")
            try:
                # Создаем Redis клиент для UserHistory
                from core.redis_manager import RedisManager
                redis_manager = RedisManager()
                await redis_manager.initialize()
                self.user_history = UserHistory(redis_manager)
                # UserHistory не требует отдельной инициализации
                logger.info("✅ История пользователей инициализирована")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации истории: {e}")
                self.user_history = None

            # Обновляем ссылку на историю в обработчиках
            if self.user_history:
                self.message_handlers.user_history = self.user_history
                self.command_handlers.user_history = self.user_history
                self.document_handlers.user_history = self.user_history
                self.user_management.user_history = self.user_history

            # Обновляем ссылку на async_redis в обработчиках
            self.document_handlers.async_redis = self.async_redis

            # Настройка команд бота
            logger.info("🔧 Настройка команд бота...")
            await self.setup_bot_commands()

            # Запуск обработки уведомлений в фоне
            logger.info("🔧 Запуск обработки уведомлений...")
            asyncio.create_task(self._notification_loop())

            # Получение информации о боте
            bot_info = await self.bot.get_me()
            logger.info(f"✅ Бот @{bot_info.username} запущен и готов к работе!")
            telegram_logger.info(f"Бот @{bot_info.username} начал работу")

            # Запуск polling
            await self.dp.start_polling(self.bot, skip_updates=True)

        except Exception as e:
            logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
            raise
        finally:
            # Закрытие соединений при завершении
            if self.async_redis:
                await self.async_redis.close()
            logger.info("🔒 Telegram бот остановлен")

    async def _notification_loop(self):
        """Цикл обработки уведомлений в фоне."""
        while True:
            try:
                await self.user_management._process_notification_queue()
                await asyncio.sleep(10)  # Проверяем каждые 10 секунд
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле уведомлений: {e}")
                await asyncio.sleep(30)  # При ошибке ждем дольше

    async def stop(self):
        """Корректная остановка бота."""
        try:
            logger.info("🔄 Остановка Telegram бота...")

            # Закрытие Redis соединения
            if self.async_redis:
                await self.async_redis.close()
                logger.info("✅ Redis соединение закрыто")

            # Очистка обрабатывающихся пользователей
            self.processing_users.clear()

            logger.info("✅ Telegram бот корректно остановлен")

        except Exception as e:
            logger.error(f"❌ Ошибка при остановке бота: {e}")

    def get_health_status(self) -> dict:
        """Получение статуса здоровья бота."""
        return {
            "bot_running": self.bot is not None,
            "redis_connected": self.async_redis is not None,
            "user_history_available": self.user_history is not None,
            "processing_users": len(self.processing_users),
            "handlers_registered": {
                "message_handlers": self.message_handlers is not None,
                "command_handlers": self.command_handlers is not None,
                "document_handlers": self.document_handlers is not None,
                "user_management": self.user_management is not None
            }
        }


async def main():
    """Основная функция запуска бота."""
    # Получаем токен из переменных окружения
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        return

    # Создание и запуск бота
    bot = TelegramBot(token)

    try:
        await bot.start_polling()
    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал остановки")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        await bot.stop()


if __name__ == "__main__":
    from core.logging_config import configure_logging

    configure_logging()

    # Запуск бота
    asyncio.run(main())