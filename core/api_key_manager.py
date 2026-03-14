#!/usr/bin/env python3
"""
API Key Manager с автоматической ротацией (МИГРАЦИЯ v2.0)
Поддерживает Google Gemini и OpenAI API ключи

МИГРАЦИЯ v2.0 (13.10.2025):
- Добавлена поддержка OpenAI provider
- Сохранена обратная совместимость с Gemini (legacy)
- Multi-provider architecture (можно переключаться между Gemini и OpenAI)
"""

import logging
import os
import secrets
from typing import List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class APIKeyManager:
    """
    Менеджер API ключей с автоматической ротацией (multi-provider).

    Поддерживаемые провайдеры:
    - "gemini": Google Gemini API (legacy)
    - "openai": OpenAI API (GPT-4/GPT-5)

    Функции:
    - Пул из N ключей (6 для Gemini, N для OpenAI)
    - Автоматическая ротация при 429 ошибках
    - Round-robin распределение для балансировки нагрузки
    - Tracking использования каждого ключа
    """

    API_KEYS = []

    def __init__(self, provider: str = "openai"):
        """
        Args:
            provider: "gemini" (legacy) или "openai" (default после миграции)
        """
        self.provider = provider.lower()
        self._current_index = 0

        # Если явный список не задан, подтянем ключи из переменных окружения
        if not self.API_KEYS:
            self._load_keys_from_env()

        self._key_usage = {i: 0 for i in range(len(self.API_KEYS))}
        self._key_errors = {i: 0 for i in range(len(self.API_KEYS))}
        self._last_error_time = {i: None for i in range(len(self.API_KEYS))}

        logger.info(f" API Key Manager initialized: provider={self.provider}, keys={len(self.API_KEYS)}")

    def _load_keys_from_env(self):
        """Загрузить ключи из переменных окружения (multi-provider)."""
        env_keys = []

        if self.provider == "openai":
            # OpenAI API keys
            index = 1
            while True:
                value = os.getenv(f"OPENAI_API_KEY_{index}")
                if not value:
                    break
                env_keys.append(value)
                index += 1

            # Primary OpenAI key
            primary_key = os.getenv("OPENAI_API_KEY")
            if primary_key:
                env_keys.append(primary_key)

        elif self.provider == "gemini":
            # Gemini API keys (legacy)
            index = 1
            while True:
                value = os.getenv(f"GEMINI_API_KEY_{index}")
                if not value:
                    break
                env_keys.append(value)
                index += 1

            # Primary Gemini key
            primary_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if primary_key:
                env_keys.append(primary_key)

        else:
            raise ValueError(f"Unsupported provider: {self.provider}. Use 'gemini' or 'openai'")

        if env_keys:
            # Удаляем дубликаты, сохраняя порядок
            seen = set()
            unique_keys = []
            for key in env_keys:
                if key not in seen:
                    seen.add(key)
                    unique_keys.append(key)
            self.API_KEYS = unique_keys

    def get_next_key(self) -> str:
        """
        Получить следующий ключ по round-robin
        Возвращает ключ с наименьшим использованием
        """
        # Round-robin для балансировки
        if not self.API_KEYS:
            self._load_keys_from_env()
            if not self.API_KEYS:
                raise RuntimeError("No API keys configured. Set GEMINI_API_KEY or GEMINI_API_KEY_N")

        key = self.API_KEYS[self._current_index]
        self._key_usage[self._current_index] += 1

        logger.debug(f" Using API key #{self._current_index + 1} (usage: {self._key_usage[self._current_index]})")

        self._current_index = (self._current_index + 1) % len(self.API_KEYS)

        return key

    def get_random_key(self) -> str:
        """Получить случайный ключ (для параллельных запросов)"""
        if not self.API_KEYS:
            return self.get_next_key()

        index = secrets.randbelow(len(self.API_KEYS))
        self._key_usage[index] += 1

        logger.debug(f" Random API key #{index + 1} selected")
        return self.API_KEYS[index]

    def report_error(self, api_key: str, is_quota_error: bool = False):
        """
        Отчёт об ошибке для конкретного ключа

        Args:
            api_key: Ключ, который вызвал ошибку
            is_quota_error: Является ли это 429/quota ошибкой
        """
        try:
            if not api_key or len(api_key) < 4:
                logger.warning(" Invalid API key provided for error report")
                return
            index = self.API_KEYS.index(api_key) if self.API_KEYS else None
            if index is None:
                logger.warning(" Unknown API key in error report")
                return

            self._key_errors[index] += 1

            if is_quota_error:
                self._last_error_time[index] = datetime.now()
                logger.warning(f" Quota error on API key #{index + 1} (total errors: {self._key_errors[index]})")
            else:
                logger.error(f" Error on API key #{index + 1}")

        except ValueError:
            logger.warning(" Unknown API key in error report")

    def get_available_keys(self) -> List[str]:
        """
        Получить список доступных ключей (без недавних quota ошибок)

        Returns:
            Список ключей, которые не имели quota ошибок в последние 5 минут
        """
        if not self.API_KEYS:
            self._load_keys_from_env()
            if not self.API_KEYS:
                return []

        available = []
        now = datetime.now()

        for i, key in enumerate(self.API_KEYS):
            last_error = self._last_error_time[i]

            if last_error is None or (now - last_error) > timedelta(minutes=5):
                available.append(key)

        if not available:
            logger.warning(" All keys have recent errors, returning all keys")
            return self.API_KEYS.copy()

        logger.debug(f" {len(available)}/{len(self.API_KEYS)} keys available")
        return available

    def get_key_with_least_usage(self) -> str:
        """Получить ключ с наименьшим количеством использований"""
        if not self.API_KEYS:
            return self.get_next_key()

        min_usage = min(self._key_usage.values())

        for i, usage in self._key_usage.items():
            if usage == min_usage:
                self._key_usage[i] += 1
                logger.debug(f" Least used key #{i + 1} (usage: {usage})")
                return self.API_KEYS[i]

        return self.get_next_key()

    def get_stats(self) -> dict:
        """Получить статистику использования ключей"""
        available_keys = self.get_available_keys()
        total_keys = len(self.API_KEYS)
        if total_keys == 0:
            self._load_keys_from_env()
            total_keys = len(self.API_KEYS)

        return {
            "total_keys": total_keys,
            "current_index": self._current_index,
            "usage_per_key": self._key_usage.copy(),
            "errors_per_key": self._key_errors.copy(),
            "available_keys": len(available_keys),
            "total_usage": sum(self._key_usage.values()),
            "total_errors": sum(self._key_errors.values()),
        }

    def print_stats(self):
        """Вывести статистику в консоль"""
        stats = self.get_stats()

        print("\n" + "="*60)
        print(" API KEY MANAGER STATISTICS")
        print("="*60)
        print(f"Total Keys: {stats['total_keys']}")
        print(f"Available Keys: {stats['available_keys']}/{stats['total_keys']}")
        print(f"Total Usage: {stats['total_usage']}")
        print(f"Total Errors: {stats['total_errors']}")
        if self.API_KEYS:
            print()
            print("Per-Key Breakdown:")
            for i in range(len(self.API_KEYS)):
                usage = stats['usage_per_key'][i]
                errors = stats['errors_per_key'][i]
                key_preview = self.API_KEYS[i][:20] + "..."
                print(f" Key #{i+1}: {key_preview} - Usage: {usage:3d}, Errors: {errors:2d}")
        print("="*60)


# Глобальные singleton instances (по одному для каждого provider)
_key_managers = {}


def get_key_manager(provider: str = "openai") -> APIKeyManager:
    """
    Получить singleton instance APIKeyManager для провайдера.

    Args:
        provider: "openai" (default) или "gemini" (legacy)

    Returns:
        APIKeyManager: Singleton instance для провайдера
    """
    global _key_managers

    if provider not in _key_managers:
        _key_managers[provider] = APIKeyManager(provider=provider)

    return _key_managers[provider]


def get_api_key(provider: str = "openai") -> str:
    """
    Получить API ключ для провайдера (удобный shortcut).

    Args:
        provider: "openai" (default) или "gemini" (legacy)

    Returns:
        str: API key
    """
    # Пробуем из environment
    if provider == "openai":
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            return env_key
    elif provider == "gemini":
        env_key = os.getenv("GEMINI_API_KEY")
        if env_key:
            return env_key

    # Fallback на key manager
    return get_key_manager(provider=provider).get_next_key()
