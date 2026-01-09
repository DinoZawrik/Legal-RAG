"""Прокси-вызовы к внутренним сервисам."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

from services.gateway.models import ServiceRequest

if TYPE_CHECKING:  # pragma: no cover
    from services.gateway.app import APIGateway


def register(gateway: "APIGateway") -> None:
    app = gateway.app

    @app.post("/api/service/{service_name}")
    async def call_service(service_name: str, request: ServiceRequest, http_request: Request):
        try:
            client_ip = http_request.client.host
            if not await gateway._check_rate_limit(client_ip):
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            service = gateway.registry.get_service(service_name)
            if not service:
                raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

            service_request = {
                "type": request.action,
                "request_id": request.request_id or uuid.uuid4().hex[:8],
                **request.data,
            }

            return await service.handle_request(service_request)
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Service call error: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))
