#!/usr/bin/env python3
"""
🤖 Telegram Bot Command Handlers
Модуль для обработки команд телеграм-бота.

Включает функциональность:
- Команда /start
- Команда /help
- Команда /upload
- Команда /request_access
- Команда /clear
"""

import logging
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.admin_panel import is_admin, check_user_permission_async
from bot.keyboards import create_clear_chat_confirmation_keyboard, DOC_TYPE_PREFIX
from bot.database_helpers import create_permission_request
from bot.states import Form

logger = logging.getLogger(__name__)
telegram_logger = logging.getLogger("telegram_operations")


class CommandHandlers:
    """Класс для обработки команд в Telegram боте."""

    def __init__(self, bot_instance):
        """Инициализация обработчика команд."""
        self.bot = bot_instance.bot
        self.user_history = bot_instance.user_history
        self.notification_service = bot_instance.notification_service

    async def start_command(self, message: Message):
        """Обработчик команды /start."""
        try:
            user_id = message.from_user.id
            username = message.from_user.username or "Пользователь"
            first_name = message.from_user.first_name or ""

            telegram_logger.info(f"Команда /start от пользователя {user_id} (@{username})")

            # Проверяем права доступа
            has_permission = await check_user_permission_async(user_id)
            admin_status = " (👑 Администратор)" if await is_admin(user_id) else ""

            if has_permission:
                welcome_text = f"""🚀 Добро пожаловать, {first_name}!{admin_status}

🤖 Я ваш помощник по работе с правовыми документами.

📋 **Что я умею:**
• Отвечать на вопросы по загруженным документам
• Обрабатывать PDF файлы и презентации
• Анализировать архивы документов
• Предоставлять подробные правовые консультации

🔍 **Как пользоваться:**
1. Загрузите документы через команду /upload
2. Задавайте вопросы обычными сообщениями
3. Используйте /help для подробной справки

✅ У вас есть права доступа к системе."""
            else:
                welcome_text = f"""🚀 Добро пожаловать, {first_name}!

🤖 Я помощник по работе с правовыми документами.

❗ **Внимание:** У вас пока нет прав доступа к системе.

🔑 **Для получения доступа:**
• Используйте команду /request_access
• Укажите причину запроса доступа
• Дождитесь одобрения администратора

📞 **Обратитесь к администратору** для ускорения процесса."""

            await message.answer(welcome_text)

            # Добавляем сообщение в историю если есть права доступа
            if has_permission and self.user_history:
                await self.user_history.add_message(
                    user_id=user_id,
                    role="system",
                    content="Пользователь выполнил команду /start",
                    message_type="command"
                )

        except Exception as e:
            logger.error(f"❌ Ошибка в start_command: {e}")
            await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")

    async def help_command(self, message: Message):
        """Обработчик команды /help."""
        try:
            user_id = message.from_user.id
            telegram_logger.info(f"Команда /help от пользователя {user_id}")

            # Проверяем права доступа
            has_permission = await check_user_permission_async(user_id)

            if has_permission:
                help_text = """❓ **Справка по использованию бота**

🔍 **Основные возможности:**
• Загрузка и анализ PDF документов
• Обработка презентаций PowerPoint
• Работа с архивами документов
• Ответы на правовые вопросы

📋 **Доступные команды:**
• `/start` - Начать работу с ботом
• `/upload` - Загрузить документ для анализа
• `/clear` - Очистить историю сообщений
• `/request_access` - Запросить права доступа
• `/help` - Показать эту справку

📄 **Поддерживаемые форматы:**
• PDF документы
• PowerPoint презентации (.pptx)
• ZIP архивы с документами

🤖 **Как задавать вопросы:**
• Формулируйте вопросы четко и конкретно
• Укажите контекст, если необходимо
• Используйте ключевые слова из документов

💡 **Примеры вопросов:**
• "Что говорится о налоговых льготах в документе?"
• "Какие требования к оформлению договора?"
• "Найди информацию о штрафах"

⚡ **Для оптимальной работы:**
• Загружайте качественные PDF файлы
• Убедитесь, что текст в документах читаемый
• Подождите завершения обработки перед новыми запросами"""
            else:
                help_text = """❓ **Справка по использованию бота**

❗ У вас нет прав доступа к основным функциям.

🔑 **Для получения доступа:**
• Используйте команду `/request_access`
• Опишите цель использования системы
• Дождитесь одобрения администратора

📞 **Контакты:**
Обратитесь к администратору системы для получения доступа.

📋 **Доступные команды:**
• `/start` - Начать работу с ботом
• `/request_access` - Запросить права доступа
• `/help` - Показать эту справку"""

            await message.answer(help_text)

            # Добавляем в историю если есть права доступа
            if has_permission and self.user_history:
                await self.user_history.add_message(
                    user_id=user_id,
                    role="system",
                    content="Пользователь выполнил команду /help",
                    message_type="command"
                )

        except Exception as e:
            logger.error(f"❌ Ошибка в help_command: {e}")
            await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")

    async def upload_command(self, message: Message, state: FSMContext):
        """Обработчик команды /upload."""
        try:
            user_id = message.from_user.id
            telegram_logger.info(f"Команда /upload от пользователя {user_id}")

            # Проверяем права доступа
            has_permission = await check_user_permission_async(user_id)
            if not has_permission:
                await message.answer("❌ У вас нет прав для загрузки документов. Используйте /request_access.")
                return

            upload_text = """📄 **Загрузка документов**

📋 **Поддерживаемые форматы:**
• PDF документы (.pdf)
• PowerPoint презентации (.pptx)
• ZIP архивы с документами (.zip)

📤 **Как загрузить:**
1. Прикрепите файл к сообщению (не фото!)
2. Выберите тип документа
3. Дождитесь завершения обработки

⚡ **Требования к файлам:**
• Размер до 20 МБ
• Текст должен быть читаемым (не скан)
• Качественное содержимое

💡 **Совет:** После загрузки документа вы сможете задавать вопросы по его содержимому."""

            await message.answer(upload_text)

            # Добавляем в историю
            if self.user_history:
                await self.user_history.add_message(
                    user_id=user_id,
                    role="system",
                    content="Пользователь выполнил команду /upload",
                    message_type="command"
                )

        except Exception as e:
            logger.error(f"❌ Ошибка в upload_command: {e}")
            await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")

    async def request_access_command(self, message: Message):
        """Обработчик команды /request_access."""
        try:
            user_id = message.from_user.id
            username = message.from_user.username or "Unknown"
            first_name = message.from_user.first_name or "Unknown"

            telegram_logger.info(f"Команда /request_access от пользователя {user_id} (@{username})")

            # Проверяем, есть ли уже права доступа
            has_permission = await check_user_permission_async(user_id)
            if has_permission:
                await message.answer("✅ У вас уже есть права доступа к системе!")
                return

            # Создаем запрос на доступ
            request_result = await create_permission_request(
                user_id=user_id,
                username=username,
                first_name=first_name,
                reason="Запрос доступа через команду /request_access"
            )

            if request_result['success']:
                # Отправляем уведомление администраторам
                await self.notification_service.notify_permission_request(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    reason="Запрос доступа через команду"
                )

                success_text = f"""✅ **Запрос на доступ отправлен!**

👤 **Информация о запросе:**
• ID пользователя: {user_id}
• Username: @{username}
• Имя: {first_name}

⏳ **Что дальше:**
• Ваш запрос отправлен администраторам
• Вы получите уведомление о решении
• Обычно рассмотрение занимает несколько часов

📞 **Для ускорения:** Обратитесь к администратору напрямую."""

                await message.answer(success_text)
            else:
                error_message = request_result.get('message', 'Неизвестная ошибка')
                await message.answer(f"❌ Ошибка при создании запроса: {error_message}")

        except Exception as e:
            logger.error(f"❌ Ошибка в request_access_command: {e}")
            await message.answer("❌ Произошла ошибка при создании запроса. Попробуйте еще раз.")

    async def clear_command(self, message: Message):
        """Обработчик команды /clear."""
        try:
            user_id = message.from_user.id
            telegram_logger.info(f"Команда /clear от пользователя {user_id}")

            # Проверяем права доступа
            has_permission = await check_user_permission_async(user_id)
            if not has_permission:
                await message.answer("❌ У вас нет прав для использования этой команды. Используйте /request_access.")
                return

            confirmation_text = """🗑️ **Очистка истории сообщений**

⚠️ **Внимание:** Будут удалены все сообщения из истории чата, кроме загруженных документов.

📋 **Что будет удалено:**
• Все текстовые сообщения
• История вопросов и ответов
• Контекст предыдущих диалогов

📄 **Что останется:**
• Загруженные документы
• Обработанные файлы
• Настройки доступа

❓ **Вы уверены, что хотите продолжить?**"""

            keyboard = create_clear_chat_confirmation_keyboard()
            await message.answer(confirmation_text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"❌ Ошибка в clear_command: {e}")
            await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")