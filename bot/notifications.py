"""Модуль уведомлений и подписок"""

from typing import List, Set
import asyncio
from datetime import datetime



class NotificationManager:
    """Менеджер уведомлений"""

    def __init__(self, unified_storage.redis.client, bot):
        self.redis = unified_storage.redis.client
        self.bot = bot

    async def subscribe_to_document_updates(self, user_id: int, document_id: str):
        """Подписка на обновления документа"""
        sub_key = f"subscriptions:doc:{document_id}"
        await self.redis.sadd(sub_key, user_id)
        await self.redis.expire(sub_key, 86400 * 30)  # 30 дней

    async def subscribe_to_keywords(self, user_id: int, keywords: List[str]):
        """Подписка на ключевые слова"""
        for keyword in keywords:
            sub_key = f"subscriptions:keyword:{keyword.lower()}"
            await self.redis.sadd(sub_key, user_id)
            await self.redis.expire(sub_key, 86400 * 30)

    async def notify_document_processed(self, document_id: str, document_name: str):
        """Уведомление о завершении обработки документа"""
        sub_key = f"subscriptions:doc:{document_id}"
        subscribers = await self.redis.smembers(sub_key)

        for user_id_str in subscribers:
            user_id = int(user_id_str)
            try:
                await self.bot.send_message(
                    user_id,
                    f" *Документ обработан*\n\n"
                    f" {document_name}\n"
                    f" ID: `{document_id}`\n\n"
                    f"Теперь вы можете задавать вопросы по этому документу!",
                    parse_mode="Markdown",
                )
            except Exception as e:
                # Логируем ошибки отправки
                print(f"Failed to send notification to {user_id}: {e}")

    async def notify_keyword_match(self, keyword: str, document_name: str, context: str):
        """Уведомление о найденном ключевом слове в новом документе"""
        sub_key = f"subscriptions:keyword:{keyword.lower()}"
        subscribers = await self.redis.smembers(sub_key)

        for user_id_str in subscribers:
            user_id = int(user_id_str)
            try:
                await self.bot.send_message(
                    user_id,
                    f" *Найдено совпадение*\n\n"
                    f"Ключевое слово: `{keyword}`\n"
                    f" Документ: {document_name}\n"
                    f" Контекст: {context[:200]}...\n\n"
                    f"Используйте /documents для работы с документом",
                    parse_mode="Markdown",
                )
            except Exception as e:
                print(f"Failed to send keyword notification to {user_id}: {e}")

    async def get_user_subscriptions(self, user_id: int) -> dict:
        """Получает подписки пользователя"""
        # Поиск по всем ключам подписок
        doc_subs = []
        keyword_subs = []

        # Это упрощенная версия, в реальности нужна более эффективная индексация
        all_keys = await self.redis.keys("subscriptions:*")

        for key in all_keys:
            if await self.redis.sismember(key, user_id):
                if key.startswith("subscriptions:doc:"):
                    doc_id = key.split(":")[-1]
                    doc_subs.append(doc_id)
                elif key.startswith("subscriptions:keyword:"):
                    keyword = key.split(":")[-1]
                    keyword_subs.append(keyword)

        return {"documents": doc_subs, "keywords": keyword_subs}
