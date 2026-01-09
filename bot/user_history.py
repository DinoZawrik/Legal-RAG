"""Модуль для работы с историей пользователя"""

import json
from typing import List, Dict
from datetime import datetime



class UserHistory:
    """Класс для управления историей пользователя"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def save_question(self, user_id: int, question: str, answer: str, documents_used: List[str]):
        """Сохраняет вопрос и ответ в историю"""
        history_key = f"user:{user_id}:history"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": answer[:500] + "..." if len(answer) > 500 else answer,  # Сокращаем для экономии места
            "documents_used": documents_used,
            "id": str(hash(question + str(datetime.now()))),
        }

        # Используем правильный redis client
        redis_client = self.redis.client if hasattr(self.redis, 'client') and self.redis.client else self.redis

        # Сохраняем последние 50 вопросов
        await redis_client.lpush(history_key, json.dumps(entry))
        await redis_client.ltrim(history_key, 0, 49)
        await redis_client.expire(history_key, 86400 * 30)  # Храним 30 дней

    async def search_history(self, user_id: int, query: str, limit: int = 10) -> List[Dict]:
        """Поиск по истории вопросов"""
        history_key = f"user:{user_id}:history"
        redis_client = self.redis.client if hasattr(self.redis, 'client') and self.redis.client else self.redis
        history_raw = await redis_client.lrange(history_key, 0, -1)

        if not history_raw:
            return []

        history = [json.loads(entry) for entry in history_raw]

        # Простой поиск по подстроке (можно улучшить с помощью нечеткого поиска)
        query_lower = query.lower()
        matching = []

        for entry in history:
            if query_lower in entry["question"].lower() or query_lower in entry["answer"].lower():
                matching.append(entry)

        return matching[:limit]

    async def get_recent_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получает недавнюю историю пользователя"""
        history_key = f"user:{user_id}:history"
        redis_client = self.redis.client if hasattr(self.redis, 'client') and self.redis.client else self.redis
        history_raw = await redis_client.lrange(history_key, 0, limit - 1)

        if not history_raw:
            return []

        return [json.loads(entry) for entry in history_raw]

    async def clear_history(self, user_id: int) -> bool:
        """Очищает всю историю пользователя"""
        try:
            history_key = f"user:{user_id}:history"
            redis_client = self.redis.client if hasattr(self.redis, 'client') and self.redis.client else self.redis
            await redis_client.delete(history_key)
            return True
        except Exception as e:
            print(f"Ошибка при очистке истории пользователя {user_id}: {e}")
            return False

    async def save_message_id(self, user_id: int, message_id: int, message_type: str = "bot"):
        """Сохраняет ID сообщения для последующего удаления"""
        try:
            messages_key = f"user:{user_id}:messages"
            redis_client = self.redis.client if hasattr(self.redis, 'client') and self.redis.client else self.redis
            
            message_data = {
                "message_id": message_id,
                "type": message_type,
                "timestamp": datetime.now().isoformat()
            }
            
            # Сохраняем последние 200 сообщений
            await redis_client.lpush(messages_key, json.dumps(message_data))
            await redis_client.ltrim(messages_key, 0, 199)
            await redis_client.expire(messages_key, 86400 * 7)  # Храним 7 дней
            
        except Exception as e:
            print(f"Ошибка при сохранении ID сообщения: {e}")

    async def get_message_ids(self, user_id: int, message_type: str = "bot") -> List[int]:
        """Получает ID сообщений для удаления"""
        try:
            messages_key = f"user:{user_id}:messages"
            redis_client = self.redis.client if hasattr(self.redis, 'client') and self.redis.client else self.redis
            messages_raw = await redis_client.lrange(messages_key, 0, -1)
            
            if not messages_raw:
                return []
            
            message_ids = []
            for msg_data in messages_raw:
                try:
                    msg_info = json.loads(msg_data)
                    if msg_info.get("type") == message_type:
                        message_ids.append(msg_info["message_id"])
                except json.JSONDecodeError:
                    continue
                    
            return message_ids
            
        except Exception as e:
            print(f"Ошибка при получении ID сообщений: {e}")
            return []

    async def clear_message_ids(self, user_id: int):
        """Очищает сохраненные ID сообщений"""
        try:
            messages_key = f"user:{user_id}:messages"
            redis_client = self.redis.client if hasattr(self.redis, 'client') and self.redis.client else self.redis
            await redis_client.delete(messages_key)
        except Exception as e:
            print(f"Ошибка при очистке ID сообщений: {e}")
