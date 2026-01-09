"""
Система уведомлений для запросов прав доступа.

Этот модуль отвечает за отправку уведомлений администраторам и пользователям
о статусе запросов на получение прав доступа.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from aiogram import Bot
from core.infrastructure_suite import SETTINGS

logger = logging.getLogger(__name__)


class PermissionNotifications:
    """Класс для управления уведомлениями о запросах прав доступа"""
    
    def __init__(self, bot: Bot):
        """Инициализация системы уведомлений"""
        self.bot = bot
        self.admin_chat_ids = self._get_admin_chat_ids()
        self.notification_queue = asyncio.Queue()
        self.is_processing = False
    
    def _get_admin_chat_ids(self) -> List[int]:
        """Получение ID чатов администраторов"""
        try:
            # TELEGRAM_ADMIN_IDS уже обработан как List[int] в настройках
            admin_ids = SETTINGS.TELEGRAM_ADMIN_IDS or []
            logger.info(f"📢 Найдено {len(admin_ids)} администраторов для уведомлений")
            return admin_ids
        except Exception as e:
            logger.error(f"❌ Ошибка при получении TELEGRAM_ADMIN_IDS: {e}")
            return []
    
    async def notify_admins_new_request(self, request_data: Dict[str, Any]):
        """Уведомление администраторов о новом запросе на права"""
        try:
            if not self.admin_chat_ids:
                logger.warning("⚠️ Нет администраторов для уведомления")
                return
            
            # Формируем сообщение о новом запросе
            message = self._format_new_request_message(request_data)
            
            # Отправляем уведомление каждому администратору
            for admin_id in self.admin_chat_ids:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=message,
                        parse_mode="Markdown"
                    )
                    logger.info(f"📤 Уведомление отправлено администратору {admin_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки уведомления администратору {admin_id}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при уведомлении администраторов: {e}")
    
    async def notify_user_request_status(self, telegram_id: int, status: str, request_data: Dict[str, Any]):
        """Уведомление пользователя о статусе запроса"""
        try:
            # Формируем сообщение о статусе
            message = self._format_status_message(status, request_data)
            
            # Отправляем уведомление пользователю
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown"
            )
            
            logger.info(f"📤 Уведомление о статусе отправлено пользователю {telegram_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления пользователю {telegram_id}: {e}")
    
    async def notify_admins_batch_processed(self, batch_result: Dict[str, Any]):
        """Уведомление администраторов о массовой обработке запросов"""
        try:
            if not self.admin_chat_ids:
                logger.warning("⚠️ Нет администраторов для уведомления")
                return
            
            # Формируем сообщение о массовой обработке
            message = self._format_batch_processed_message(batch_result)
            
            # Отправляем уведомление каждому администратору
            for admin_id in self.admin_chat_ids:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=message,
                        parse_mode="Markdown"
                    )
                    logger.info(f"📤 Уведомление о массовой обработке отправлено администратору {admin_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки уведомления администратору {admin_id}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при уведомлении администраторов о массовой обработке: {e}")
    
    def _format_new_request_message(self, request_data: Dict[str, Any]) -> str:
        """Формирование сообщения о новом запросе"""
        user_info = request_data.get('display_name', f"ID: {request_data.get('telegram_id')}")
        permission = request_data.get('requested_permission', 'upload_documents')
        message = request_data.get('request_message', '')
        request_id = request_data.get('id')
        requested_at = request_data.get('requested_at')
        
        # Форматируем дату
        date_str = "неизвестно"
        if requested_at:
            try:
                dt = datetime.fromisoformat(requested_at.replace('Z', '+00:00'))
                date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        message_text = f"""🔑 *Новый запрос на права доступа*

👤 **Пользователь:** {user_info}
📋 **ID запроса:** #{request_id}
🔒 **Тип прав:** {permission}
📅 **Запрошено:** {date_str}
💬 **Сообщение:**
{message}

👉 Перейти к обработке: http://localhost:8090/"""
        
        return message_text
    
    def _format_status_message(self, status: str, request_data: Dict[str, Any]) -> str:
        """Формирование сообщения о статусе запроса"""
        user_info = request_data.get('display_name', f"ID: {request_data.get('telegram_id')}")
        permission = request_data.get('requested_permission', 'upload_documents')
        request_id = request_data.get('id')
        admin_comment = request_data.get('admin_comment', '')
        
        # Определяем эмодзи и текст статуса
        if status == 'approved':
            emoji = "✅"
            status_text = "одобрен"
        elif status == 'rejected':
            emoji = "❌"
            status_text = "отклонен"
        else:
            emoji = "⏳"
            status_text = "обработан"
        
        message_text = f"""{emoji} *Статус вашего запроса*

👤 **Пользователь:** {user_info}
📋 **ID запроса:** #{request_id}
🔒 **Тип прав:** {permission}
{emoji} **Статус:** {status_text}
"""
        
        if admin_comment:
            message_text += f"\n💬 **Комментарий администратора:**\n{admin_comment}"
        
        if status == 'approved':
            message_text += f"\n\n🎉 Поздравляем! Вам выданы права на {permission}. Теперь вы можете использовать команду /upload для загрузки документов."
        elif status == 'rejected':
            message_text += f"\n\n😔 К сожалению, ваш запрос был отклонен. Вы можете попробовать запросить права снова через некоторое время."
        
        return message_text
    
    def _format_batch_processed_message(self, batch_result: Dict[str, Any]) -> str:
        """Формирование сообщения о массовой обработке"""
        processed_count = batch_result.get('processed_count', 0)
        failed_count = batch_result.get('failed_count', 0)
        action = batch_result.get('action', 'processed')
        processed_by = batch_result.get('processed_by', 'admin')
        
        # Определяем эмодзи и текст действия
        if action == 'approve':
            emoji = "✅"
            action_text = "одобрено"
        elif action == 'reject':
            emoji = "❌"
            action_text = "отклонено"
        else:
            emoji = "⚙️"
            action_text = "обработано"
        
        message_text = f"""{emoji} *Массовая обработка запросов*

📊 **Результаты:**
{emoji} **Успешно:** {processed_count}
❌ **Не удалось:** {failed_count}

🔧 **Действие:** {action_text}
👤 **Обработано:** {processed_by}

👉 [Перейти к списку запросов](http://localhost:8080/admin/permission-requests/list)"""
        
        return message_text
    
    async def add_to_queue(self, notification_type: str, data: Dict[str, Any]):
        """Добавление уведомления в очередь"""
        try:
            await self.notification_queue.put({
                'type': notification_type,
                'data': data,
                'timestamp': datetime.utcnow().isoformat()
            })
            logger.info(f"📝 Уведомление добавлено в очередь: {notification_type}")
        except Exception as e:
            logger.error(f"❌ Ошибка добавления уведомления в очередь: {e}")
    
    async def process_queue(self):
        """Обработка очереди уведомлений"""
        if self.is_processing:
            logger.warning("⚠️ Обработка очереди уже идет")
            return
        
        self.is_processing = True
        logger.info("🚀 Начало обработки очереди уведомлений")
        
        try:
            while not self.notification_queue.empty():
                try:
                    # Получаем уведомление из очереди
                    notification = await self.notification_queue.get()
                    notification_type = notification['type']
                    data = notification['data']
                    
                    logger.info(f"📤 Обработка уведомления: {notification_type}")
                    
                    # Обрабатываем уведомление в зависимости от типа
                    if notification_type == 'new_request':
                        await self.notify_admins_new_request(data)
                    elif notification_type == 'request_status':
                        telegram_id = data.get('telegram_id')
                        status = data.get('status')
                        if telegram_id and status:
                            await self.notify_user_request_status(telegram_id, status, data)
                    elif notification_type == 'batch_processed':
                        await self.notify_admins_batch_processed(data)
                    else:
                        logger.warning(f"⚠️ Неизвестный тип уведомления: {notification_type}")
                    
                    # Подтверждаем обработку
                    self.notification_queue.task_done()
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки уведомления: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при обработке очереди: {e}")
        finally:
            self.is_processing = False
            logger.info("✅ Обработка очереди уведомлений завершена")
    
    async def start_processing(self):
        """Запуск фоновой обработки очереди уведомлений"""
        logger.info("🚀 Запуск фоновой обработки очереди уведомлений")
        
        # Запускаем обработку в отдельной задаче
        asyncio.create_task(self.process_queue())
    
    async def stop_processing(self):
        """Остановка фоновой обработки очереди уведомлений"""
        logger.info("🛑 Остановка фоновой обработки очереди уведомлений")
        self.is_processing = False


# Глобальный экземпляр системы уведомлений
_notifications_instance = None


async def get_permission_notifications(bot: Bot) -> PermissionNotifications:
    """Получение глобального экземпляра системы уведомлений"""
    global _notifications_instance
    if _notifications_instance is None:
        _notifications_instance = PermissionNotifications(bot)
        await _notifications_instance.start_processing()
    return _notifications_instance


async def notify_admins_new_request(bot: Bot, request_data: Dict[str, Any]):
    """Уведомление администраторов о новом запросе (синхронная обертка)"""
    try:
        notifications = await get_permission_notifications(bot)
        await notifications.add_to_queue('new_request', request_data)
    except Exception as e:
        logger.error(f"❌ Ошибка при уведомлении администраторов: {e}")


async def notify_user_request_status(bot: Bot, telegram_id: int, status: str, request_data: Dict[str, Any]):
    """Уведомление пользователя о статусе запроса (синхронная обертка)"""
    try:
        notifications = await get_permission_notifications(bot)
        await notifications.add_to_queue('request_status', {
            'telegram_id': telegram_id,
            'status': status,
            'request_data': request_data
        })
    except Exception as e:
        logger.error(f"❌ Ошибка при уведомлении пользователя: {e}")


async def notify_admins_batch_processed(bot: Bot, batch_result: Dict[str, Any]):
    """Уведомление администраторов о массовой обработке (синхронная обертка)"""
    try:
        notifications = await get_permission_notifications(bot)
        await notifications.add_to_queue('batch_processed', batch_result)
    except Exception as e:
        logger.error(f"❌ Ошибка при уведомлении о массовой обработке: {e}")