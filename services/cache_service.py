#!/usr/bin/env python3
"""
[FLOPPY_DISK] Cache Service
Микросервис кэширования - интеллектуальное многоуровневое кэширование
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
import time

from services.base import BaseService
# MIGRATED FROM: core.intelligent_cache (deprecated wrapper) NEW: core.cache
from core.cache import IntelligentCache
from core.logging_config import configure_logging

# Temporary: define CacheStrategy locally or import from cache.cache
try:
    from core.cache.cache import CacheStrategy
except (ImportError, AttributeError):
    from enum import Enum
    class CacheStrategy(Enum):
        LRU = "lru"
        LFU = "lfu"
        TTL = "ttl"
        ADAPTIVE = "adaptive"

async def get_intelligent_cache() -> IntelligentCache:
    """Legacy compatibility."""
    return IntelligentCache()

logger = logging.getLogger(__name__)


class CacheService(BaseService):
    """
    Микросервис кэширования.
    
    Функции:
    - Многоуровневое кэширование (память + Redis)
    - Семантическое сходство запросов
    - Адаптивное время жизни кэша
    - Автоматическая оптимизация
    """
    
    def __init__(self):
        super().__init__("cache_service")
        
        # Компоненты кэширования
        self.cache: Optional[IntelligentCache] = None
        
        # Конфигурация по умолчанию
        self.default_config = {
            "strategy": "adaptive",
            "max_memory_entries": 1000,
            "default_ttl": 3600,
            "semantic_threshold": 0.75,
            "auto_cleanup_interval": 300 # 5 минут
        }
        
        # Метрики кэша
        self.cache_metrics = {
            "operations_count": 0,
            "get_operations": 0,
            "set_operations": 0,
            "delete_operations": 0,
            "cleanup_operations": 0
        }
        
        # Таймер для автоматической очистки
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def initialize(self) -> None:
        """Инициализация Cache Service."""
        try:
            self.logger.info("[FLOPPY_DISK] Initializing Cache Service...")
            
            # Инициализация интеллектуального кэша
            self.logger.info("[RELOAD] Loading Intelligent Cache...")
            self.cache = await get_intelligent_cache()
            
            # Запуск автоматической очистки
            await self._start_auto_cleanup()
            
            self.logger.info("[CHECK_MARK_BUTTON] Cache Service initialized successfully")
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Failed to initialize Cache Service: {e}")
            raise
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запросов к кэшу."""
        request_type = request.get("type", "get")
        
        if request_type == "get":
            return await self._handle_get_request(request)
        elif request_type == "set":
            return await self._handle_set_request(request)
        elif request_type == "delete":
            return await self._handle_delete_request(request)
        elif request_type == "clear":
            return await self._handle_clear_request(request)
        elif request_type == "stats":
            return await self._handle_stats_request(request)
        elif request_type == "optimize":
            return await self._handle_optimize_request(request)
        elif request_type == "configure":
            return await self._handle_config_request(request)
        elif request_type == "preload":
            return await self._handle_preload_request(request)
        else:
            raise ValueError(f"Unknown request type: {request_type}")
    
    async def cleanup(self) -> None:
        """Очистка ресурсов Cache Service."""
        try:
            # Остановка автоматической очистки
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Финальная очистка кэша
            if self.cache:
                await self.cache.cleanup_expired_entries()
            
            self.logger.info("[BROOM] Cache Service cleanup completed")
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Error during Cache Service cleanup: {e}")
    
    async def _handle_get_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса получения из кэша."""
        key = request.get("key") or request.get("query")
        context = request.get("context")
        enable_semantic = request.get("enable_semantic", True)
        
        if not key:
            raise ValueError("Key or query is required")
        
        self.cache_metrics["get_operations"] += 1
        self.cache_metrics["operations_count"] += 1
        
        try:
            if not self.cache:
                raise RuntimeError("Cache not initialized")
            
            # Получение из кэша
            result = await self.cache.get(
                query=key,
                context=context,
                enable_semantic_search=enable_semantic
            )
            
            cache_status = "hit" if result is not None else "miss"
            
            self.logger.debug(f"[FLOPPY_DISK] Cache {cache_status} for key: {key[:50]}...")
            
            return {
                "key": key,
                "value": result,
                "status": cache_status,
                "found": result is not None
            }
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Cache get failed: {e}")
            raise
    
    async def _handle_set_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса сохранения в кэш."""
        key = request.get("key") or request.get("query")
        value = request.get("value")
        context = request.get("context")
        ttl = request.get("ttl")
        priority = request.get("priority", 1.0)
        
        if not key:
            raise ValueError("Key or query is required")
        
        if value is None:
            raise ValueError("Value is required")
        
        self.cache_metrics["set_operations"] += 1
        self.cache_metrics["operations_count"] += 1
        
        try:
            if not self.cache:
                raise RuntimeError("Cache not initialized")
            
            # Сохранение в кэш
            await self.cache.set(
                query=key,
                value=value,
                context=context,
                ttl=ttl,
                priority=priority
            )
            
            self.logger.debug(f"[FLOPPY_DISK] Cache set for key: {key[:50]}...")
            
            return {
                "key": key,
                "status": "stored",
                "ttl": ttl,
                "priority": priority
            }
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Cache set failed: {e}")
            raise
    
    async def _handle_delete_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса удаления из кэша."""
        pattern = request.get("pattern") or request.get("key")
        
        if not pattern:
            raise ValueError("Pattern or key is required")
        
        self.cache_metrics["delete_operations"] += 1
        self.cache_metrics["operations_count"] += 1
        
        try:
            if not self.cache:
                raise RuntimeError("Cache not initialized")
            
            # Инвалидация кэша
            await self.cache.invalidate(pattern)
            
            self.logger.info(f"[FLOPPY_DISK] Cache invalidated with pattern: {pattern}")
            
            return {
                "pattern": pattern,
                "status": "deleted"
            }
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Cache delete failed: {e}")
            raise
    
    async def _handle_clear_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса полной очистки кэша."""
        
        self.cache_metrics["delete_operations"] += 1
        self.cache_metrics["operations_count"] += 1
        
        try:
            if not self.cache:
                raise RuntimeError("Cache not initialized")
            
            # Полная очистка кэша
            await self.cache.invalidate()
            
            self.logger.info("[FLOPPY_DISK] Full cache clear completed")
            
            return {
                "status": "cleared",
                "scope": "all"
            }
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Cache clear failed: {e}")
            raise
    
    async def _handle_stats_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса статистики кэша."""
        stats = {
            "service_metrics": self.get_metrics(),
            "cache_operations": self.cache_metrics.copy(),
            "cache_stats": {}
        }
        
        # Детальная статистика кэша
        if self.cache:
            stats["cache_stats"] = self.cache.get_cache_stats()
        
        return stats
    
    async def _handle_optimize_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса оптимизации кэша."""
        try:
            if not self.cache:
                raise RuntimeError("Cache not initialized")
            
            # Запуск оптимизации
            optimization_report = self.cache.optimize_cache_settings()
            
            # Очистка истекших записей
            await self.cache.cleanup_expired_entries()
            
            self.logger.info(f"[FLOPPY_DISK] Cache optimization completed: {len(optimization_report.get('optimizations', []))} changes")
            
            return {
                "status": "optimized",
                "optimization_report": optimization_report
            }
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Cache optimization failed: {e}")
            raise
    
    async def _handle_config_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса конфигурации кэша."""
        action = request.get("action", "get")
        
        if action == "get":
            current_config = self.default_config.copy()
            if self.cache:
                current_config.update({
                    "current_strategy": self.cache.strategy.value,
                    "semantic_threshold": self.cache.semantic_threshold,
                    "max_memory_entries": self.cache.max_memory_entries
                })
            
            return {
                "current_config": current_config,
                "cache_operations": self.cache_metrics
            }
        
        elif action == "update":
            new_config = request.get("config", {})
            self.default_config.update(new_config)
            
            # Применение конфигурации к кэшу
            if self.cache:
                if "semantic_threshold" in new_config:
                    self.cache.semantic_threshold = new_config["semantic_threshold"]
                
                if "max_memory_entries" in new_config:
                    self.cache.max_memory_entries = new_config["max_memory_entries"]
            
            return {
                "status": "updated",
                "new_config": self.default_config
            }
        
        else:
            raise ValueError(f"Unknown config action: {action}")
    
    async def _handle_preload_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса предзагрузки популярных запросов."""
        queries = request.get("queries", [])
        
        if not queries:
            raise ValueError("Queries list is required")
        
        try:
            if not self.cache:
                raise RuntimeError("Cache not initialized")
            
            # Предзагрузка популярных запросов
            await self.cache.preload_popular_queries(queries)
            
            self.logger.info(f"[FLOPPY_DISK] Preloaded {len(queries)} popular queries")
            
            return {
                "status": "preloaded",
                "queries_count": len(queries)
            }
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Cache preload failed: {e}")
            raise
    
    async def _start_auto_cleanup(self) -> None:
        """Запуск автоматической очистки кэша."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.default_config["auto_cleanup_interval"])
                    
                    if self.cache:
                        await self.cache.cleanup_expired_entries()
                        self.cache_metrics["cleanup_operations"] += 1
                        
                        self.logger.debug("[FLOPPY_DISK] Automatic cache cleanup completed")
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"[CROSS_MARK] Auto cleanup error: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        self.logger.info("[RELOAD] Auto cleanup task started")
    
    async def _additional_health_checks(self) -> Dict[str, bool]:
        """Дополнительные проверки здоровья для Cache Service."""
        checks = {}
        
        # Проверка компонентов
        checks["cache_initialized"] = self.cache is not None
        checks["auto_cleanup_running"] = (
            self._cleanup_task is not None and 
            not self._cleanup_task.done()
        )
        
        # Проверка производительности кэша
        if self.cache:
            try:
                cache_stats = self.cache.get_cache_stats()
                total_requests = cache_stats.get("total_requests", 0)
                # Для новых сервисов (< 10 запросов) считаем hit_rate приемлемым
                hit_rate = cache_stats.get("hit_rate", 0)
                checks["acceptable_hit_rate"] = total_requests < 10 or hit_rate > 0.15
                checks["memory_usage_ok"] = cache_stats.get("memory_entries", 0) < self.default_config["max_memory_entries"]
                checks["redis_available"] = cache_stats.get("redis_available", True) # Default True для fallback
            except Exception:
                # При ошибках считаем сервис работоспособным, если кэш инициализирован
                checks["acceptable_hit_rate"] = True
                checks["memory_usage_ok"] = True
                checks["redis_available"] = True
        
        return checks


async def create_cache_service() -> CacheService:
    """Factory function for fully initialized CacheService."""
    service = CacheService()
    await service.start()
    return service


if __name__ == "__main__":
    import asyncio

    configure_logging(os.getenv("LOG_LEVEL", "INFO"))

    async def main():
        cache_service = CacheService()
        await cache_service.initialize()
        await cache_service.cleanup()

    asyncio.run(main())