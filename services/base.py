#!/usr/bin/env python3
"""
[CONSTRUCTION] Base Service Architecture
Базовые классы для микросервисной архитектуры LegalRAG
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import uuid

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Статус сервиса."""
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


@dataclass
class ServiceMetrics:
    """Метрики сервиса."""
    request_count: int = 0
    error_count: int = 0
    response_times: List[float] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    last_request_time: Optional[datetime] = None
    
    @property
    def avg_response_time(self) -> float:
        """Среднее время ответа."""
        return sum(self.response_times[-100:]) / len(self.response_times[-100:]) if self.response_times else 0.0
    
    @property
    def error_rate(self) -> float:
        """Частота ошибок."""
        return self.error_count / self.request_count if self.request_count > 0 else 0.0
    
    @property
    def uptime_seconds(self) -> float:
        """Время работы в секундах."""
        return (datetime.now() - self.start_time).total_seconds()


@dataclass
class HealthCheck:
    """Результат health check."""
    service_name: str
    status: ServiceStatus
    timestamp: datetime
    checks: Dict[str, bool] = field(default_factory=dict)
    metrics: Optional[ServiceMetrics] = None
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для API."""
        return {
            "service_name": self.service_name,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "checks": self.checks,
            "message": self.message,
            "metrics": {
                "request_count": self.metrics.request_count,
                "error_count": self.metrics.error_count,
                "avg_response_time": self.metrics.avg_response_time,
                "error_rate": self.metrics.error_rate,
                "uptime_seconds": self.metrics.uptime_seconds
            } if self.metrics else None
        }


class BaseService(ABC):
    """
    Базовый класс для всех микросервисов LegalRAG.
    
    Предоставляет:
    - Health checks
    - Metrics collection
    - Structured logging
    - Graceful shutdown
    - Service discovery integration
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.service_id = f"{service_name}-{uuid.uuid4().hex[:8]}"
        self.status = ServiceStatus.STARTING
        self.metrics = ServiceMetrics()
        self.logger = logging.getLogger(f"services.{service_name}")
        
        # Конфигурация
        self.config: Dict[str, Any] = {}
        
        # Флаг для graceful shutdown
        self._shutdown_event = asyncio.Event()
        
        self.logger.info(f"[ROCKET] Initializing service: {self.service_name} ({self.service_id})")
    
    @abstractmethod
    async def initialize(self) -> None:
        """Инициализация сервиса. Должна быть переопределена в наследниках."""
        pass
    
    @abstractmethod
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса. Должна быть переопределена в наследниках."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Очистка ресурсов при выключении сервиса."""
        pass
    
    async def start(self) -> None:
        """Запуск сервиса."""
        try:
            self.logger.info(f"[RELOAD] Starting service: {self.service_name}")
            await self.initialize()
            self.status = ServiceStatus.HEALTHY
            self.logger.info(f"[CHECK_MARK_BUTTON] Service started successfully: {self.service_name}")
            
        except Exception as e:
            self.status = ServiceStatus.UNHEALTHY
            self.logger.error(f"[CROSS_MARK] Failed to start service {self.service_name}: {e}")
            raise
    
    async def stop(self) -> None:
        """Остановка сервиса."""
        try:
            self.logger.info(f"[RELOAD] Stopping service: {self.service_name}")
            self.status = ServiceStatus.STOPPED
            self._shutdown_event.set()
            
            await self.cleanup()
            self.logger.info(f"[CHECK_MARK_BUTTON] Service stopped successfully: {self.service_name}")
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Error during service shutdown {self.service_name}: {e}")
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обертка для обработки запросов с метриками и логированием.
        """
        request_id = request.get("request_id", uuid.uuid4().hex[:8])
        start_time = time.time()
        
        # Логирование входящего запроса
        request_type = request.get("type", "unknown")
        print(f"[BASE-SERVICE] {self.service_name} - Incoming request type: {request_type}")
        self.logger.info(
            f" Incoming request",
            extra={
                "service": self.service_name,
                "request_id": request_id,
                "request_type": request_type
            }
        )
        # DEBUG: Детальный лог
        print(f"[DEBUG-ROUTING] Service={self.service_name}, Type={request_type}, Query={request.get('query', 'N/A')[:50]}")
        
        try:
            # Проверка статуса сервиса
            if self.status not in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]:
                raise Exception(f"Service {self.service_name} is not available (status: {self.status.value})")
            
            # Обработка запроса
            response = await self.process_request(request)
            
            # Обновление метрик
            response_time = time.time() - start_time
            self.metrics.request_count += 1
            self.metrics.response_times.append(response_time)
            self.metrics.last_request_time = datetime.now()
            
            # Логирование успешного ответа
            self.logger.info(
                f" Request completed successfully",
                extra={
                    "service": self.service_name,
                    "request_id": request_id,
                    "response_time": response_time,
                    "status": "success"
                }
            )
            
            return {
                "success": True,
                "data": response,
                "service": self.service_name,
                "request_id": request_id,
                "response_time": response_time
            }
            
        except Exception as e:
            # Обновление метрик ошибок
            response_time = time.time() - start_time
            self.metrics.error_count += 1
            self.metrics.response_times.append(response_time)
            
            # Логирование ошибки
            self.logger.error(
                f"[CROSS_MARK] Request failed: {str(e)}",
                extra={
                    "service": self.service_name,
                    "request_id": request_id,
                    "response_time": response_time,
                    "status": "error",
                    "error": str(e)
                },
                exc_info=True
            )
            
            return {
                "success": False,
                "error": str(e),
                "service": self.service_name,
                "request_id": request_id,
                "response_time": response_time
            }
    
    async def health_check(self) -> HealthCheck:
        """Проверка здоровья сервиса."""
        checks = {}
        overall_status = self.status
        message = ""
        
        try:
            # Базовые проверки
            checks["service_running"] = self.status != ServiceStatus.STOPPED
            checks["recent_activity"] = (
                self.metrics.last_request_time is None or
                (datetime.now() - self.metrics.last_request_time).total_seconds() < 300
            )
            checks["error_rate_acceptable"] = self.metrics.error_rate < 0.05 # Менее 5% ошибок
            
            # Дополнительные проверки (переопределяются в наследниках)
            additional_checks = await self._additional_health_checks()
            checks.update(additional_checks)
            
            # Определение общего статуса
            if all(checks.values()):
                overall_status = ServiceStatus.HEALTHY
                message = "All checks passed"
            elif any(checks.values()):
                overall_status = ServiceStatus.DEGRADED
                message = f"Some checks failed: {[k for k, v in checks.items() if not v]}"
            else:
                overall_status = ServiceStatus.UNHEALTHY
                message = "Multiple checks failed"
                
        except Exception as e:
            overall_status = ServiceStatus.UNHEALTHY
            message = f"Health check failed: {str(e)}"
            self.logger.error(f"[CROSS_MARK] Health check error for {self.service_name}: {e}")
        
        return HealthCheck(
            service_name=self.service_name,
            status=overall_status,
            timestamp=datetime.now(),
            checks=checks,
            metrics=self.metrics,
            message=message
        )
    
    async def _additional_health_checks(self) -> Dict[str, bool]:
        """Дополнительные проверки здоровья. Переопределяются в наследниках."""
        return {}
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получение метрик сервиса."""
        return {
            "service_name": self.service_name,
            "service_id": self.service_id,
            "status": self.status.value,
            "request_count": self.metrics.request_count,
            "error_count": self.metrics.error_count,
            "avg_response_time": self.metrics.avg_response_time,
            "error_rate": self.metrics.error_rate,
            "uptime_seconds": self.metrics.uptime_seconds,
            "last_request_time": self.metrics.last_request_time.isoformat() if self.metrics.last_request_time else None
        }
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Обновление конфигурации сервиса."""
        self.config.update(config)
        self.logger.info(f"[CONFIG] Configuration updated for {self.service_name}")
    
    async def wait_for_shutdown(self) -> None:
        """Ожидание сигнала для graceful shutdown."""
        await self._shutdown_event.wait()


class ServiceRegistry:
    """
    Реестр сервисов для service discovery.
    """
    
    def __init__(self):
        self.services: Dict[str, BaseService] = {}
        self.logger = logging.getLogger("services.registry")
    
    def register(self, service: BaseService) -> None:
        """Регистрация сервиса."""
        self.services[service.service_name] = service
        self.logger.info(f"[CLIPBOARD] Service registered: {service.service_name} ({service.service_id})")
    
    def unregister(self, service_name: str) -> None:
        """Отмена регистрации сервиса."""
        if service_name in self.services:
            del self.services[service_name]
            self.logger.info(f"[CLIPBOARD] Service unregistered: {service_name}")
    
    def get_service(self, service_name: str) -> Optional[BaseService]:
        """Получение сервиса по имени."""
        return self.services.get(service_name)
    
    async def get_all_health_checks(self) -> Dict[str, HealthCheck]:
        """Получение health checks для всех сервисов."""
        health_checks = {}
        
        for service_name, service in self.services.items():
            try:
                health_check = await service.health_check()
                health_checks[service_name] = health_check
            except Exception as e:
                self.logger.error(f"[CROSS_MARK] Failed to get health check for {service_name}: {e}")
                health_checks[service_name] = HealthCheck(
                    service_name=service_name,
                    status=ServiceStatus.UNHEALTHY,
                    timestamp=datetime.now(),
                    message=f"Health check failed: {str(e)}"
                )
        
        return health_checks
    
    def get_all_services(self) -> List[str]:
        """Получение списка всех зарегистрированных сервисов."""
        return list(self.services.keys())
    
    async def start_all(self) -> None:
        """Запуск всех зарегистрированных сервисов."""
        self.logger.info("[ROCKET] Starting all registered services...")
        
        for service_name, service in self.services.items():
            try:
                await service.start()
            except Exception as e:
                self.logger.error(f"[CROSS_MARK] Failed to start service {service_name}: {e}")
        
        self.logger.info("[CHECK_MARK_BUTTON] All services startup completed")
    
    async def stop_all(self) -> None:
        """Остановка всех зарегистрированных сервисов."""
        self.logger.info("[RELOAD] Stopping all registered services...")
        
        # Останавливаем в обратном порядке
        for service_name, service in reversed(list(self.services.items())):
            try:
                await service.stop()
            except Exception as e:
                self.logger.error(f"[CROSS_MARK] Failed to stop service {service_name}: {e}")
        
        self.logger.info("[CHECK_MARK_BUTTON] All services stopped")

