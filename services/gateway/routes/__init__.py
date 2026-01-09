"""Регистрация всех HTTP-маршрутов API Gateway."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import admin, health, misc, queries, service_proxy, task_queue, uploads, metrics

if TYPE_CHECKING:  # pragma: no cover
    from services.gateway.app import APIGateway


def register_all_routes(gateway: "APIGateway") -> None:
    """Подключить все группы маршрутов к экземпляру gateway."""

    misc.register(gateway)
    health.register(gateway)
    queries.register(gateway)
    service_proxy.register(gateway)
    uploads.register(gateway)
    metrics.register(gateway)
    admin.register(gateway)
    task_queue.register(gateway)
