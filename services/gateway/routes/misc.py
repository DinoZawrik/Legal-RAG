"""Простые диагностические endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from services.gateway.app import APIGateway


def register(gateway: "APIGateway") -> None:
    app = gateway.app

    @app.get("/api/simple_test")
    async def simple_test():
        return {"working": True}

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
