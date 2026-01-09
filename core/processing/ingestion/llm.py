"""LLM initialization and API key rotation utilities for ingestion pipeline."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable

from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


def get_api_key() -> str | None:
    """
    Возвращает основной API ключ Gemini из environment variables.

    Порядок поиска:
    1. GEMINI_API_KEY (primary)
    2. GOOGLE_API_KEY (fallback)

    Returns:
        API key или None если не найден
    """
    # Попытка получить из environment variables
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        logger.error(
            "❌ Google/Gemini API ключ не найден! "
            "Установите GEMINI_API_KEY или GOOGLE_API_KEY в .env файле"
        )
        return None

    return api_key


def get_backup_api_keys() -> list[str]:
    """
    Список запасных API ключей для ротации из environment variables.

    Поддерживает до 6 ключей:
    - GEMINI_API_KEY (или GOOGLE_API_KEY) - primary
    - GEMINI_API_KEY_1 (или GOOGLE_API_KEY_1)
    - GEMINI_API_KEY_2 (или GOOGLE_API_KEY_2)
    - ...
    - GEMINI_API_KEY_5 (или GOOGLE_API_KEY_5)

    Returns:
        Список API ключей (не пустых)
    """
    api_keys = []

    # Primary key
    primary = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if primary:
        api_keys.append(primary)

    # Backup keys (1-5)
    for i in range(1, 6):
        key = os.getenv(f"GEMINI_API_KEY_{i}") or os.getenv(f"GOOGLE_API_KEY_{i}")
        if key:
            api_keys.append(key)

    if not api_keys:
        logger.error(
            "❌ Нет доступных API ключей для ротации! "
            "Установите GEMINI_API_KEY и/или GEMINI_API_KEY_1-5 в .env файле"
        )

    return api_keys


def retry_with_key_rotation(
    func: Callable[..., Any], *args: Any, max_retries: int = 5, **kwargs: Any
) -> Any:
    """Выполняет функцию с ротацией API ключей при ошибках квоты."""

    api_keys = get_backup_api_keys()
    for retry_count in range(max_retries):
        current_key_index = retry_count % len(api_keys)
        current_key = api_keys[current_key_index]

        try:
            if hasattr(func, "__self__") and hasattr(func.__self__, "google_api_key"):
                func.__self__.google_api_key = current_key  # type: ignore[attr-defined]

            logger.info(
                "🔑 Attempt %s/%s with API key #%s",
                retry_count + 1,
                max_retries,
                current_key_index + 1,
            )
            return func(*args, **kwargs)

        except Exception as exc:  # pragma: no cover - rely on runtime
            error_message = str(exc).lower()
            if any(token in error_message for token in ("429", "quota", "rate limit")):
                logger.warning(
                    "⚠️ API quota error on key #%s, rotating to next key...",
                    current_key_index + 1,
                )
                if retry_count < max_retries - 1:
                    time.sleep(5)
                continue
            raise

    raise RuntimeError(f"❌ All {max_retries} API keys exhausted, unable to complete request")


api_key = get_api_key()

llm_settings = {
    "model": "gemini-2.5-flash",
    "temperature": 0,
    "google_api_key": api_key,
    "request_timeout": int(os.getenv("GEMINI_REQUEST_TIMEOUT", "300")),
    "max_retries": int(os.getenv("GEMINI_MAX_RETRIES", "3")),
}

llm_vision = ChatGoogleGenerativeAI(**llm_settings)
llm_structured = ChatGoogleGenerativeAI(**llm_settings)
llm_json_parser = ChatGoogleGenerativeAI(**llm_settings)


__all__ = [
    "api_key",
    "get_api_key",
    "get_backup_api_keys",
    "llm_json_parser",
    "llm_structured",
    "llm_vision",
    "retry_with_key_rotation",
]
