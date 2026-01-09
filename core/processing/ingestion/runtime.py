"""Runtime helpers for ingestion pipeline (Redis, storage, cancellation)."""

from __future__ import annotations

import json
import logging
from typing import Optional

import redis

from core.storage_coordinator import create_storage_coordinator
from core.infrastructure_suite import SETTINGS as settings

logger = logging.getLogger(__name__)


try:  # pragma: no cover - depends on environment
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=getattr(settings, "REDIS_PASSWORD", None),
        decode_responses=True,
    )
except Exception as exc:  # fallback to localhost for safety
    logger.warning(
        "Redis init failed with configured host %s: %s. Falling back to localhost.",
        getattr(settings, "REDIS_HOST", "unknown"),
        exc,
    )
    redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

unified_storage = None


def get_unified_storage():
    """Лениво инициализирует unified storage."""

    global unified_storage  # pylint: disable=global-statement
    if unified_storage is None:
        unified_storage = await create_storage_coordinator()
    return unified_storage


def _check_cancel_requested(task_id: Optional[str]) -> bool:
    """Проверяет запрошена ли отмена задачи."""

    if not task_id:
        return False

    task_status_raw = redis_client.get(f"task:{task_id}")
    if not task_status_raw:
        return False

    try:
        task_status = json.loads(task_status_raw)
    except json.JSONDecodeError:
        logger.warning("Invalid task status json for task %s: %s", task_id, task_status_raw)
        return False

    return task_status.get("cancel_requested", False)


__all__ = [
    "_check_cancel_requested",
    "get_unified_storage",
    "redis_client",
    "unified_storage",
]
