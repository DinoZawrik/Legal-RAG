"""Модуль утилит для пагинации в Telegram боте"""

import math
from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup


from bot.keyboards import create_search_pagination_keyboard


class PaginationManager:
    """Менеджер пагинации для результатов поиска"""

    def __init__(self, items_per_page: int = 10):
        """
        Инициализация менеджера пагинации

        Args:
            items_per_page: Количество элементов на одной странице
        """
        self.items_per_page = items_per_page

    def paginate_results(self, items: List[Any], page: int = 1) -> Dict[str, Any]:
        """
        Разбивает список элементов на страницы

        Args:
            items: Список элементов для пагинации
            page: Номер страницы (начиная с 1)

        Returns:
            Dict: Словарь с пагинированными данными
        """
        if not items:
            return {
                "items": [],
                "current_page": 1,
                "total_pages": 1,
                "total_items": 0,
                "has_next": False,
                "has_prev": False,
                "start_index": 0,
                "end_index": 0,
            }

        total_items = len(items)
        total_pages = math.ceil(total_items / self.items_per_page)

        # Ограничиваем номер страницы
        page = max(1, min(page, total_pages))

        start_index = (page - 1) * self.items_per_page
        end_index = min(start_index + self.items_per_page, total_items)

        page_items = items[start_index:end_index]

        return {
            "items": page_items,
            "current_page": page,
            "total_pages": total_pages,
            "total_items": total_items,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "start_index": start_index,
            "end_index": end_index,
        }

    def create_pagination_keyboard(
        self, current_page: int, total_pages: int, search_id: str
    ) -> Optional[InlineKeyboardMarkup]:
        """
        Создает клавиатуру пагинации

        Args:
            current_page: Текущая страница
            total_pages: Общее количество страниц
            search_id: Идентификатор поиска

        Returns:
            InlineKeyboardMarkup: Клавиатура пагинации или None если пагинация не нужна
        """
        if total_pages <= 1:
            return None

        return create_search_pagination_keyboard(current_page, total_pages, search_id)

    def get_page_info_text(self, pagination_data: Dict[str, Any]) -> str:
        """
        Формирует текстовую информацию о текущей странице

        Args:
            pagination_data: Данные пагинации

        Returns:
            str: Текст с информацией о странице
        """
        current_page = pagination_data.get("current_page", 1)
        total_pages = pagination_data.get("total_pages", 1)
        total_items = pagination_data.get("total_items", 0)
        start_index = pagination_data.get("start_index", 0)
        end_index = pagination_data.get("end_index", 0)

        if total_items == 0:
            return "❌ Ничего не найдено"

        return f"📄 Страница {current_page} из {total_pages} (Показаны {start_index + 1}-{end_index} из {total_items} результатов)"


# Глобальный экземпляр менеджера пагинации
pagination_manager = PaginationManager()


def get_pagination_manager(items_per_page: int = 10) -> PaginationManager:
    """
    Получает глобальный экземпляр менеджера пагинации

    Args:
        items_per_page: Количество элементов на странице

    Returns:
        PaginationManager: Экземпляр менеджера пагинации
    """
    global pagination_manager

    if pagination_manager is None or pagination_manager.items_per_page != items_per_page:
        pagination_manager = PaginationManager(items_per_page)

    return pagination_manager


def paginate_search_results(results: List[Dict], page: int = 1, items_per_page: int = 10) -> Dict[str, Any]:
    """
    Пагинация результатов поиска

    Args:
        results: Список результатов поиска
        page: Номер страницы
        items_per_page: Количество элементов на странице

    Returns:
        Dict: Пагинированные данные
    """
    manager = get_pagination_manager(items_per_page)
    return manager.paginate_results(results, page)


def format_pagination_info(pagination_data: Dict[str, Any]) -> str:
    """
    Форматирует информацию о пагинации для отображения

    Args:
        pagination_data: Данные пагинации

    Returns:
        str: Отформатированная информация
    """
    manager = get_pagination_manager()
    return manager.get_page_info_text(pagination_data)


def create_search_pagination(search_id: str, current_page: int, total_pages: int) -> Optional[InlineKeyboardMarkup]:
    """
    Создает клавиатуру пагинации для поиска

    Args:
        search_id: Идентификатор поиска
        current_page: Текущая страница
        total_pages: Общее количество страниц

    Returns:
        InlineKeyboardMarkup: Клавиатура пагинации
    """
    manager = get_pagination_manager()
    return manager.create_pagination_keyboard(current_page, total_pages, search_id)


# Утилиты для работы с кэшем пагинации
class PaginationCache:
    """Кэш для хранения результатов пагинации"""

    def __init__(self, unified_storage.redis.client=None):
        """
        Инициализация кэша пагинации

        Args:
            unified_storage.redis.client: Клиент Redis для кэширования
        """
        self.unified_storage.redis.client = unified_storage.redis.client

    async def cache_search_results(self, search_id: str, results: List[Any], ttl: int = 1800):
        """
        Кэширует результаты поиска

        Args:
            search_id: Идентификатор поиска
            results: Результаты поиска
            ttl: Время жизни кэша в секундах (по умолчанию 30 минут)
        """
        if not self.unified_storage.redis.client:
            return

        try:
            import json

            cache_key = f"search_results:{search_id}"
            await self.unified_storage.redis.client.setex(cache_key, ttl, json.dumps(results, ensure_ascii=False))
        except Exception as e:
            # Логируем ошибку, но не прерываем выполнение
            print(f"Ошибка кэширования результатов поиска: {e}")

    async def get_cached_search_results(self, search_id: str) -> Optional[List[Any]]:
        """
        Получает кэшированные результаты поиска

        Args:
            search_id: Идентификатор поиска

        Returns:
            List[Any]: Кэшированные результаты или None
        """
        if not self.unified_storage.redis.client:
            return None

        try:
            import json

            cache_key = f"search_results:{search_id}"
            cached_data = await self.unified_storage.redis.client.get(cache_key)

            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            # Логируем ошибку, но не прерываем выполнение
            print(f"Ошибка получения кэшированных результатов: {e}")
            return None

    async def cache_pagination_state(self, user_id: int, search_id: str, pagination_data: Dict, ttl: int = 3600):
        """
        Кэширует состояние пагинации для пользователя

        Args:
            user_id: ID пользователя
            search_id: Идентификатор поиска
            pagination_data: Данные пагинации
            ttl: Время жизни кэша в секундах (по умолчанию 1 час)
        """
        if not self.unified_storage.redis.client:
            return

        try:
            import json

            cache_key = f"pagination_state:{user_id}:{search_id}"
            await self.unified_storage.redis.client.setex(cache_key, ttl, json.dumps(pagination_data, ensure_ascii=False))
        except Exception as e:
            # Логируем ошибку, но не прерываем выполнение
            print(f"Ошибка кэширования состояния пагинации: {e}")

    async def get_cached_pagination_state(self, user_id: int, search_id: str) -> Optional[Dict]:
        """
        Получает кэшированное состояние пагинации

        Args:
            user_id: ID пользователя
            search_id: Идентификатор поиска

        Returns:
            Dict: Кэшированное состояние пагинации или None
        """
        if not self.unified_storage.redis.client:
            return None

        try:
            import json

            cache_key = f"pagination_state:{user_id}:{search_id}"
            cached_data = await self.unified_storage.redis.client.get(cache_key)

            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            # Логируем ошибку, но не прерываем выполнение
            print(f"Ошибка получения кэшированного состояния пагинации: {e}")
            return None


# Глобальный экземпляр кэша пагинации
pagination_cache = None


def get_pagination_cache(unified_storage.redis.client=None) -> PaginationCache:
    """
    Получает глобальный экземпляр кэша пагинации

    Args:
        unified_storage.redis.client: Клиент Redis

    Returns:
        PaginationCache: Экземпляр кэша пагинации
    """
    global pagination_cache

    if pagination_cache is None:
        pagination_cache = PaginationCache(unified_storage.redis.client)

    return pagination_cache
