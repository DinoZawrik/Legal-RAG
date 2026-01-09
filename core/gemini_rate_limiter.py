#!/usr/bin/env python3
"""Async rate limiter for Gemini API calls."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Dict

__all__ = ["GeminiRateLimiter"]


def _rpm_to_interval(rpm_env: str, default_rpm: float) -> float:
    """Convert requests-per-minute to seconds between requests."""

    try:
        rpm = float(os.getenv(rpm_env, default_rpm))
        if rpm <= 0:
            return 0.0
        return 60.0 / rpm
    except ValueError:
        return 60.0 / default_rpm


_DEFAULT_INTERVALS: Dict[str, float] = {
    "flash": _rpm_to_interval("GEMINI_FLASH_RPM", 10.0),
    "flash-lite": _rpm_to_interval("GEMINI_FLASH_LITE_RPM", 15.0),
}


class GeminiRateLimiter:
    """Simple async rate limiter per Gemini model family."""

    _intervals: Dict[str, float] = _DEFAULT_INTERVALS.copy()
    _locks: Dict[str, asyncio.Lock] = {model: asyncio.Lock() for model in _intervals}
    _last_call: Dict[str, float] = {model: 0.0 for model in _intervals}

    @classmethod
    def set_interval(cls, model: str, interval: float) -> None:
        """Override interval for a model family at runtime."""

        cls._intervals[model] = max(0.0, interval)
        if model not in cls._locks:
            cls._locks[model] = asyncio.Lock()
        if model not in cls._last_call:
            cls._last_call[model] = 0.0

    @classmethod
    async def wait(cls, model: str) -> None:
        """Await until the model is allowed to issue the next request."""

        interval = cls._intervals.get(model)
        if not interval:
            return

        if model not in cls._locks:
            cls._locks[model] = asyncio.Lock()
        if model not in cls._last_call:
            cls._last_call[model] = 0.0

        async with cls._locks[model]:
            now = time.monotonic()
            elapsed = now - cls._last_call[model]
            sleep_time = interval - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                now = time.monotonic()
            cls._last_call[model] = now



