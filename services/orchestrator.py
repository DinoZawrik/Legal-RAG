#!/usr/bin/env python3
"""
[THEATER] Services Orchestrator
Оркестратор запуска и управления микросервисами LegalRAG
"""

import asyncio
import signal
import sys
import logging
import os
from contextlib import asynccontextmanager
from typing import List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Импорты сервисов
from services.base import ServiceRegistry, ServiceStatus
from services.gateway import APIGateway, create_api_gateway
from services.search_service import create_search_service
from services.inference_service import create_inference_service
from services.cache_service import create_cache_service
from services.storage_service import create_storage_service

from core.logging_config import configure_logging

logger = logging.getLogger(__name__)


class ServicesOrchestrator:
    """
    Оркестратор управления микросервисами.
    
    Функции:
    - Последовательный запуск сервисов
    - Graceful shutdown
    - Health monitoring
    - Service discovery
    """
    
    def __init__(self):
        self.registry = ServiceRegistry()
        self.api_gateway: Optional[APIGateway] = None
        self.services_started = False
        self.shutdown_event = asyncio.Event()
        
        # Конфигурация запуска
        self.config = {
            "gateway_host": os.getenv("GATEWAY_HOST", "0.0.0.0"),
            "gateway_port": int(os.getenv("GATEWAY_PORT", "8080")),
            "startup_timeout": int(os.getenv("STARTUP_TIMEOUT", "30")),
            "health_check_interval": int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))
        }
    
    async def start_all_services(self) -> None:
        """Запуск всех микросервисов в правильном порядке."""
        logger.info("[THEATER] Starting LegalRAG Microservices Architecture")
        logger.info("=" * 60)
        
        try:
            # 1. Базовые сервисы (Storage, Cache)
            logger.info("[DOCS] Phase 1: Starting core services...")
            await self._start_core_services()
            
            # 2. Бизнес-логика сервисы (Search, Inference)
            logger.info("[AI] Phase 2: Starting business logic services...")
            await self._start_business_services()
            
            # 3. API Gateway
            logger.info("[DOOR] Phase 3: Starting API Gateway...")
            await self._start_api_gateway()
            
            # 4. Health monitoring
            logger.info(" Phase 4: Starting health monitoring...")
            await self._start_health_monitoring()
            
            self.services_started = True
            logger.info("[PARTY_POPPER] All services started successfully!")
            logger.info("=" * 60)
            
            await self._print_startup_summary()
            
        except Exception as e:
            logger.error(f"[CROSS_MARK] Failed to start services: {e}")
            await self.shutdown_all_services()
            raise
    
    async def _start_core_services(self) -> None:
        """Запуск базовых сервисов."""
        
        # Storage Service
        logger.info("[FILE_CABINET] Starting Storage Service...")
        storage_service = await create_storage_service()
        self.registry.register(storage_service)
        logger.info("[CHECK_MARK_BUTTON] Storage Service registered")
        
        # Cache Service
        logger.info("[FLOPPY_DISK] Starting Cache Service...")
        cache_service = await create_cache_service()
        self.registry.register(cache_service)
        logger.info("[CHECK_MARK_BUTTON] Cache Service registered")
        
        # Проверка здоровья базовых сервисов
        await asyncio.sleep(2)
        await self._verify_core_services_health()
    
    async def _start_business_services(self) -> None:
        """Запуск бизнес-логики сервисов."""
        
        # Inference Service
        logger.info("[AI] Starting Inference Service...")
        inference_service = await create_inference_service()
        self.registry.register(inference_service)
        logger.info("[CHECK_MARK_BUTTON] Inference Service registered")
        
        # Search Service
        logger.info("[SEARCH] Starting Search Service...")
        search_service = await create_search_service()
        self.registry.register(search_service)
        logger.info("[CHECK_MARK_BUTTON] Search Service registered")
        
        # Проверка здоровья бизнес сервисов
        await asyncio.sleep(2)
        await self._verify_business_services_health()
    
    async def _start_api_gateway(self) -> None:
        """Запуск API Gateway."""
        self.api_gateway = create_api_gateway()
        self.api_gateway.registry = self.registry
        await self.api_gateway.start()
        self.registry.register(self.api_gateway)
        logger.info("[CHECK_MARK_BUTTON] API Gateway registered")
    
    async def _start_health_monitoring(self) -> None:
        """Запуск мониторинга здоровья сервисов."""
        asyncio.create_task(self._health_monitoring_loop())
        logger.info("[CHECK_MARK_BUTTON] Health monitoring started")
    
    async def _verify_core_services_health(self) -> None:
        """Проверка здоровья базовых сервисов."""
        core_services = ["storage_service", "cache_service"]
        
        for service_name in core_services:
            service = self.registry.get_service(service_name)
            if not service:
                raise RuntimeError(f"Core service {service_name} not found")
            
            health = await service.health_check()
            if health.status != ServiceStatus.HEALTHY:
                raise RuntimeError(f"Core service {service_name} is unhealthy: {health.message}")
            
            logger.info(f"[CHECK_MARK_BUTTON] {service_name} health verified")
    
    async def _verify_business_services_health(self) -> None:
        """Проверка здоровья бизнес-сервисов."""
        business_services = ["inference_service", "search_service"]
        
        for service_name in business_services:
            service = self.registry.get_service(service_name)
            if not service:
                raise RuntimeError(f"Business service {service_name} not found")
            
            health = await service.health_check()
            if health.status != ServiceStatus.HEALTHY:
                logger.warning(f"[WARNING] Business service {service_name} has issues: {health.message}")
            else:
                logger.info(f"[OK] {service_name} health verified")
    
    async def _print_startup_summary(self) -> None:
        """Вывод сводки о запущенных сервисах."""
        services = self.registry.get_all_services()
        
        logger.info("[CONFIG] Service Registry Summary:")
        for service_name in services:
            service = self.registry.get_service(service_name)
            if service:
                logger.info(f" • {service_name}: {service.status.value}")
        
        logger.info(f"[API] Gateway: http://{self.config['gateway_host']}:{self.config['gateway_port']}")
        logger.info(f"[HEALTH] Endpoint: http://{self.config['gateway_host']}:{self.config['gateway_port']}/health/all")
        logger.info(f"[METRICS] Endpoint: http://{self.config['gateway_host']}:{self.config['gateway_port']}/metrics")
    
    async def _health_monitoring_loop(self) -> None:
        """Цикл мониторинга здоровья сервисов."""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(self.config["health_check_interval"])
                
                if self.shutdown_event.is_set():
                    break
                
                # Проверка здоровья всех сервисов
                unhealthy_services = []
                for service_name in self.registry.get_all_services():
                    service = self.registry.get_service(service_name)
                    if service:
                        try:
                            health = await service.health_check()
                            if health.status != ServiceStatus.HEALTHY:
                                unhealthy_services.append(service_name)
                        except Exception as e:
                            logger.error(f"[CROSS_MARK] Health check failed for {service_name}: {e}")
                            unhealthy_services.append(service_name)
                
                if unhealthy_services:
                    logger.warning(f"[WARNING] Unhealthy services detected: {unhealthy_services}")
                else:
                    logger.debug(" All services healthy")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CROSS_MARK] Health monitoring error: {e}")
    
    async def shutdown_all_services(self) -> None:
        """Graceful shutdown всех сервисов."""
        logger.info("[STOP_SIGN] Shutting down all services...")
        
        # Установка флага shutdown
        self.shutdown_event.set()
        
        # Список сервисов в обратном порядке запуска
        services_order = [
            "api_gateway",
            "search_service", 
            "inference_service",
            "cache_service",
            "storage_service"
        ]
        
        for service_name in services_order:
            try:
                service = self.registry.get_service(service_name)
                if service:
                    logger.info(f"[STOP_SIGN] Stopping {service_name}...")
                    await service.stop()
                    logger.info(f"[CHECK_MARK_BUTTON] {service_name} stopped")
            except Exception as e:
                logger.error(f"[CROSS_MARK] Error stopping {service_name}: {e}")
        
        logger.info("[CHECK_MARK_BUTTON] All services shutdown completed")
    
    async def run_server(self) -> None:
        """Запуск сервера API Gateway."""
        if not self.api_gateway:
            raise RuntimeError("API Gateway not initialized")
        
        logger.info(f"[ROCKET] Starting server on {self.config['gateway_host']}:{self.config['gateway_port']}")
        await self.api_gateway.start_server(
            host=self.config["gateway_host"],
            port=self.config["gateway_port"]
        )


async def main():
    """Основная функция запуска всех сервисов."""
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    orchestrator = ServicesOrchestrator()
    
    # Обработчики сигналов для graceful shutdown
    def signal_handler():
        logger.info("[STOP_SIGN] Received shutdown signal")
        asyncio.create_task(orchestrator.shutdown_all_services())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, lambda s, f: signal_handler())
        except AttributeError:
            # Windows не поддерживает SIGTERM
            pass
    
    try:
        # Запуск всех сервисов
        await orchestrator.start_all_services()
        
        # Запуск API Gateway сервера
        await orchestrator.run_server()
        
    except KeyboardInterrupt:
        logger.info("[BLACK_SQUARE_BUTTON] Keyboard interrupt received")
    except Exception as e:
        logger.error(f"[CROSS_MARK] Fatal error: {e}")
        sys.exit(1)
    finally:
        await orchestrator.shutdown_all_services()


if __name__ == "__main__":
    asyncio.run(main())