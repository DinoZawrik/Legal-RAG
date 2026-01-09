#!/usr/bin/env python3
"""
🤖 Telegram Bot User Management
Модуль для управления пользователями и уведомлениями.

Включает функциональность:
- Обработка колбеков подтверждения
- Очистка истории чата
- Обработка уведомлений
- Управление пользователями
"""

import asyncio
import logging
from aiogram.types import CallbackQuery

from bot.admin_panel import check_user_permission_async

logger = logging.getLogger(__name__)
telegram_logger = logging.getLogger("telegram_operations")


class UserManagement:
    """Класс для управления пользователями в Telegram боте."""

    def __init__(self, bot_instance):
        """Инициализация управления пользователями."""
        self.bot = bot_instance.bot
        self.user_history = bot_instance.user_history
        self.notification_service = bot_instance.notification_service

    async def handle_clear_confirmation(self, callback_query: CallbackQuery):
        """Обработка подтверждения очистки чата."""
        try:
            user_id = callback_query.from_user.id
            telegram_logger.info(f"Подтверждение очистки от пользователя {user_id}")

            # Проверяем права доступа
            has_permission = await check_user_permission_async(user_id)
            if not has_permission:
                await callback_query.answer("❌ У вас нет прав для этого действия.")
                return

            await callback_query.answer("🗑️ Очищаем историю...")

            try:
                # Очищаем историю пользователя
                if self.user_history:
                    cleared_count = await self.user_history.clear_user_history(user_id)

                    success_text = f"""✅ **История чата очищена!**

📊 **Статистика:**
• Удалено сообщений: {cleared_count}
• Документы сохранены: Да
• Права доступа: Сохранены

💡 **Что произошло:**
• Удалены все текстовые сообщения
• Очищена история диалогов
• Загруженные документы остались в системе

🆕 **Теперь вы можете начать новый диалог!**"""
                else:
                    success_text = """✅ **История чата очищена!**

💡 Вы можете начать новый диалог с чистой историей."""

                await callback_query.message.edit_text(success_text)

                # Логируем действие
                telegram_logger.info(f"История пользователя {user_id} очищена")

            except Exception as e:
                logger.error(f"❌ Ошибка при очистке истории: {e}")
                await callback_query.message.edit_text(
                    "❌ Произошла ошибка при очистке истории. Попробуйте еще раз."
                )

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в handle_clear_confirmation: {e}")
            await callback_query.answer("❌ Произошла критическая ошибка.")

    async def handle_cancel_clear(self, callback_query: CallbackQuery):
        """Обработка отмены очистки чата."""
        try:
            user_id = callback_query.from_user.id
            telegram_logger.info(f"Отмена очистки от пользователя {user_id}")

            await callback_query.answer("❌ Очистка отменена")

            cancel_text = """❌ **Очистка истории отменена**

📝 **Ваша история диалогов сохранена:**
• Все сообщения остались на месте
• Контекст предыдущих диалогов сохранен
• Загруженные документы не затронуты

💡 **Если потребуется очистка позже**, используйте команду `/clear`"""

            await callback_query.message.edit_text(cancel_text)

        except Exception as e:
            logger.error(f"❌ Ошибка в handle_cancel_clear: {e}")
            await callback_query.answer("❌ Произошла ошибка.")

    async def _process_notification_queue(self):
        """Обработка очереди уведомлений."""
        try:
            if self.notification_service:
                await self.notification_service.process_pending_notifications()
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке уведомлений: {e}")

    async def _send_status_notification(self, user_id: int, status: str, message: str):
        """Отправка уведомления о статусе пользователю."""
        try:
            status_messages = {
                "approved": "✅ **Доступ одобрен!**\n\nВы можете использовать все функции бота.",
                "denied": "❌ **Доступ отклонен**\n\nОбратитесь к администратору за дополнительной информацией.",
                "pending": "⏳ **Запрос на рассмотрении**\n\nДождитесь решения администратора.",
                "banned": "🚫 **Доступ заблокирован**\n\nВы не можете использовать бота.",
                "warning": "⚠️ **Предупреждение**\n\nБудьте внимательны при использовании бота."
            }

            notification_text = status_messages.get(status, f"📢 **Уведомление**: {message}")

            if message:
                notification_text += f"\n\n💬 **Дополнительно**: {message}"

            await self.bot.send_message(user_id, notification_text)
            telegram_logger.info(f"Отправлено уведомление пользователю {user_id}: {status}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления пользователю {user_id}: {e}")

    async def get_user_stats(self, user_id: int) -> dict:
        """Получение статистики пользователя."""
        try:
            stats = {
                "user_id": user_id,
                "has_permission": False,
                "message_count": 0,
                "document_count": 0,
                "last_activity": None
            }

            # Проверяем права доступа
            stats["has_permission"] = await check_user_permission_async(user_id)

            # Получаем статистику из истории
            if self.user_history:
                history_stats = await self.user_history.get_user_stats(user_id)
                stats.update(history_stats)

            return stats

        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
            return {"user_id": user_id, "error": str(e)}

    async def notify_user_status_change(self, user_id: int, new_status: str, admin_message: str = None):
        """Уведомление пользователя об изменении статуса."""
        try:
            await self._send_status_notification(user_id, new_status, admin_message)

            # Добавляем в историю если есть права доступа
            if new_status == "approved" and self.user_history:
                await self.user_history.add_message(
                    user_id=user_id,
                    role="system",
                    content=f"Статус доступа изменен на: {new_status}",
                    message_type="system"
                )

        except Exception as e:
            logger.error(f"❌ Ошибка уведомления об изменении статуса для пользователя {user_id}: {e}")

    async def handle_user_activity(self, user_id: int, activity_type: str, details: str = None):
        """Обработка активности пользователя."""
        try:
            # Логируем активность
            telegram_logger.info(f"Активность пользователя {user_id}: {activity_type}")

            # Обновляем время последней активности
            if self.user_history:
                await self.user_history.update_last_activity(user_id)

            # Проверяем лимиты и ограничения (если необходимо)
            await self._check_user_limits(user_id, activity_type)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки активности пользователя {user_id}: {e}")

    async def _check_user_limits(self, user_id: int, activity_type: str):
        """Проверка лимитов пользователя."""
        try:
            # Здесь можно добавить проверки лимитов:
            # - Количество запросов в минуту
            # - Размер загруженных файлов
            # - Количество сообщений в день
            pass

        except Exception as e:
            logger.error(f"❌ Ошибка проверки лимитов для пользователя {user_id}: {e}")

    async def cleanup_inactive_users(self, days_inactive: int = 30):
        """Очистка данных неактивных пользователей."""
        try:
            if self.user_history:
                cleaned_count = await self.user_history.cleanup_inactive_users(days_inactive)
                logger.info(f"✅ Очищены данные {cleaned_count} неактивных пользователей")
                return cleaned_count
            return 0

        except Exception as e:
            logger.error(f"❌ Ошибка очистки неактивных пользователей: {e}")
            return 0

    async def export_user_data(self, user_id: int) -> dict:
        """Экспорт данных пользователя."""
        try:
            export_data = {
                "user_id": user_id,
                "exported_at": asyncio.get_event_loop().time(),
                "stats": await self.get_user_stats(user_id),
                "history": None
            }

            # Получаем историю сообщений
            if self.user_history:
                export_data["history"] = await self.user_history.get_user_history(user_id, limit=1000)

            return export_data

        except Exception as e:
            logger.error(f"❌ Ошибка экспорта данных пользователя {user_id}: {e}")
            return {"user_id": user_id, "error": str(e)}