"""Модуль системы рейтинга ответов"""

from typing import Dict, Optional
import json



class AnswerRating:
    """Система рейтинга ответов бота"""

    def __init__(self, unified_storage.redis.client):
        self.redis = unified_storage.redis.client

    async def rate_answer(self, user_id: int, question_id: str, rating: int, feedback: str = ""):
        """Сохраняет рейтинг ответа"""
        if rating not in [1, 2, 3, 4, 5]:
            raise ValueError("Рейтинг должен быть от 1 до 5")

        rating_data = {
            "user_id": user_id,
            "question_id": question_id,
            "rating": rating,
            "feedback": feedback,
            "timestamp": self._get_timestamp(),
        }

        # Сохраняем индивидуальный рейтинг
        rating_key = f"rating:{question_id}:{user_id}"
        await self.redis.set(rating_key, json.dumps(rating_data), ex=86400 * 30)

        # Обновляем общую статистику
        await self._update_global_stats(rating)

    async def get_answer_stats(self, question_id: str) -> Dict:
        """Получает статистику для конкретного ответа"""
        pattern = f"rating:{question_id}:*"
        keys = await self.redis.keys(pattern)

        if not keys:
            return {"average": 0, "count": 0, "ratings": []}

        ratings = []
        for key in keys:
            rating_data = await self.redis.get(key)
            if rating_data:
                ratings.append(json.loads(rating_data))

        if not ratings:
            return {"average": 0, "count": 0, "ratings": []}

        total = sum(r["rating"] for r in ratings)
        average = total / len(ratings)

        return {"average": round(average, 2), "count": len(ratings), "ratings": ratings}

    async def get_global_stats(self) -> Dict:
        """Получает глобальную статистику рейтингов"""
        stats_key = "global_rating_stats"
        stats_data = await self.redis.get(stats_key)

        if not stats_data:
            return {"average": 0, "total_ratings": 0, "distribution": [0, 0, 0, 0, 0]}

        return json.loads(stats_data)

    async def _update_global_stats(self, new_rating: int):
        """Обновляет глобальную статистику"""
        stats_key = "global_rating_stats"
        current_stats = await self.get_global_stats()

        # Обновляем счетчики
        current_stats["total_ratings"] += 1
        current_stats["distribution"][new_rating - 1] += 1

        # Пересчитываем средний рейтинг
        total_points = sum((i + 1) * count for i, count in enumerate(current_stats["distribution"]))
        current_stats["average"] = round(total_points / current_stats["total_ratings"], 2)

        await self.redis.set(stats_key, json.dumps(current_stats))

    def _get_timestamp(self) -> str:
        """Возвращает текущий timestamp"""
        from datetime import datetime

        return datetime.now().isoformat()

    def create_rating_keyboard(self, question_id: str):
        """Создает клавиатуру для рейтинга"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = [
            [
                InlineKeyboardButton(text="⭐", callback_data=f"rate:{question_id}:1"),
                InlineKeyboardButton(text="⭐⭐", callback_data=f"rate:{question_id}:2"),
                InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"rate:{question_id}:3"),
                InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data=f"rate:{question_id}:4"),
                InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"rate:{question_id}:5"),
            ],
            [InlineKeyboardButton(text="💬 Оставить отзыв", callback_data=f"feedback:{question_id}")],
        ]

        return InlineKeyboardMarkup(inline_keyboard=keyboard)
