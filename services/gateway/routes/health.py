"""Endpoints состояния системы и сервисов."""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from services.base import ServiceStatus

if TYPE_CHECKING:  # pragma: no cover
    from services.gateway.app import APIGateway


def _verify_health_token(request: Request) -> None:
    """Verify optional health-check bearer token for detailed endpoints."""
    expected = os.getenv("HEALTH_CHECK_TOKEN", "")
    if not expected:
        return  # Token not configured — allow access (development mode)
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {expected}":
        raise HTTPException(status_code=403, detail="Forbidden")


def register(gateway: "APIGateway") -> None:
    app = gateway.app

    @app.get("/health")
    async def health_endpoint():
        """Basic health check — always accessible."""
        try:
            health = await gateway.health_check()
            return health.to_dict()
        except Exception as exc:  # pragma: no cover
            return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(exc)})

    @app.get("/health/all")
    async def all_health_checks(request: Request):
        """Detailed health checks — require health token if configured."""
        _verify_health_token(request)
        try:
            health_checks = await gateway.registry.get_all_health_checks()
            return {name: health.to_dict() for name, health in health_checks.items()}
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": "Health check failed"})

    @app.get("/services")
    async def list_services(request: Request):
        """List registered services — require health token if configured."""
        _verify_health_token(request)
        services_info = []
        for service_name in gateway.registry.get_all_services():
            service = gateway.registry.get_service(service_name)
            if service:
                services_info.append(
                    {
                        "name": service.service_name,
                        "id": service.service_id,
                        "status": service.status.value,
                        "metrics": service.get_metrics(),
                    }
                )
        return {"services": services_info}

    @app.get("/info")
    async def get_system_info(request: Request):
        _verify_health_token(request)
        try:
            services = gateway.registry.get_all_services()
            service_details = {}
            healthy_services = 0

            for service_name in services:
                service = gateway.registry.get_service(service_name)
                if not service:
                    continue
                is_healthy = service.status == ServiceStatus.HEALTHY
                if is_healthy:
                    healthy_services += 1
                service_details[service_name] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "uptime": getattr(service, "uptime_seconds", 0),
                }

            info = {
                "name": "LegalRAG",
                "version": "v1.5.0",
                "description": "AI система для анализа российских нормативных документов",
                "architecture": "microservices",
                "services": {
                    "total": len(services),
                    "healthy": healthy_services,
                    "details": service_details,
                },
                "features": [
                    "Семантический поиск по документам",
                    "AI-генерация ответов",
                    "Интеллектуальное кэширование",
                    "Обработка архивов",
                    "Telegram бот интерфейс",
                    "Веб админ-панель",
                ],
                "timestamp": datetime.now().isoformat(),
            }

            return JSONResponse(content=info)
        except Exception as exc:
            gateway.logger.error(f"Error getting system info: {exc}")
            raise HTTPException(status_code=500, detail="Failed to get system info")

    @app.get("/status")
    async def get_system_status(request: Request):
        _verify_health_token(request)
        try:
            services = gateway.registry.get_all_services()
            healthy_services = 0

            for service_name in services:
                service = gateway.registry.get_service(service_name)
                if service and service.status == ServiceStatus.HEALTHY:
                    healthy_services += 1

            total_services = len(services)
            if total_services == 0:
                overall_status = "unhealthy"
            elif healthy_services == total_services:
                overall_status = "healthy"
            elif healthy_services > 0:
                overall_status = "degraded"
            else:
                overall_status = "unhealthy"

            status = {
                "status": overall_status,
                "message": f"{healthy_services}/{total_services} services healthy",
                "services": {
                    "total": total_services,
                    "healthy": healthy_services,
                    "unhealthy": total_services - healthy_services,
                },
                "timestamp": datetime.now().isoformat(),
                "version": "v1.5.0",
            }

            return JSONResponse(content=status)
        except Exception as exc:
            gateway.logger.error(f"Error getting system status: {exc}")
            raise HTTPException(status_code=500, detail="Failed to get system status")

    @app.get("/services/{service_name}/health")
    async def get_service_health(service_name: str, request: Request):
        _verify_health_token(request)
        try:
            service = gateway.registry.get_service(service_name)
            if not service:
                raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

            raw_metrics = getattr(service, "metrics", None)
            if raw_metrics and hasattr(raw_metrics, "request_count"):
                metrics_dict = {
                    "request_count": raw_metrics.request_count,
                    "error_count": raw_metrics.error_count,
                    "avg_response_time": raw_metrics.avg_response_time,
                    "error_rate": raw_metrics.error_rate,
                    "uptime_seconds": raw_metrics.uptime_seconds,
                }
            else:
                metrics_dict = raw_metrics if isinstance(raw_metrics, dict) else {}

            health_info = {
                "service_name": service_name,
                "status": "healthy" if service.status == ServiceStatus.HEALTHY else "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics_dict,
                "checks": gateway._get_service_specific_checks(service_name),
            }

            return JSONResponse(content=health_info)
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"Error getting service health for {service_name}: {exc}")
            raise HTTPException(status_code=500, detail=f"Failed to get health for service {service_name}")
