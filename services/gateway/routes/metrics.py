"""Маршрут для получения агрегированных метрик."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from services.gateway.app import APIGateway


def register(gateway: "APIGateway") -> None:
    app = gateway.app

    @app.get("/metrics")
    async def get_metrics():
        metrics = {"gateway": gateway.get_metrics(), "services": {}}

        for service_name in gateway.registry.get_all_services():
            service = gateway.registry.get_service(service_name)
            if service:
                metrics["services"][service_name] = service.get_metrics()

        return metrics
