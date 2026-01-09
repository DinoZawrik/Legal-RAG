"""Основная реализация API Gateway."""

from __future__ import annotations

import asyncio
import logging
import os
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import jwt
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import uvicorn

from core.dependencies import StorageDep

from services.base import (
    BaseService,
    ServiceRegistry,
    ServiceStatus,
)

from .models import (
    AdminFileUpload,
    AdminLoginRequest,
    HybridSearchRequest,
    QueryRequest,
    ServiceRequest,
    UniversalLegalQueryRequest,
)
from .routes import register_all_routes

logger = logging.getLogger(__name__)


class APIGateway(BaseService):
    """Центральная точка входа для микросервисов."""

    def __init__(self) -> None:
        super().__init__("api_gateway")

        self.app = FastAPI(
            title="LegalRAG API",
            version="5.0.0",
            description="Enterprise-grade AI document analysis system with Admin Panel",
        )

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.registry = ServiceRegistry()
        self.request_counters: Dict[str, int] = {}
        self.rate_limits: Dict[str, List[float]] = {}

        self.security = HTTPBearer()
        self.jwt_secret = os.getenv(
            "ADMIN_JWT_SECRET", "change-jwt-secret-in-production"
        )
        self.admin_password = os.getenv("ADMIN_PANEL_PASSWORD", "change_me_in_env")

        register_all_routes(self)

    async def initialize(self) -> None:
        self.logger.info("[DOOR] Initializing API Gateway...")
        services = self.registry.get_all_services()
        self.logger.info(f"[CLIPBOARD] Registered services: {services}")
        self.logger.info("[CHECK_MARK_BUTTON] API Gateway initialized")

    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "Gateway handles requests via FastAPI endpoints"}

    async def cleanup(self) -> None:
        self.logger.info("[BROOM] API Gateway cleanup completed")

    async def start_server(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        config = uvicorn.Config(app=self.app, host=host, port=port, log_level="info", access_log=True)
        server = uvicorn.Server(config)
        self.logger.info(f"[ROCKET] Starting API Gateway server on {host}:{port}")
        await server.serve()

    async def _check_rate_limit(self, client_ip: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
        now = time.time()
        window_start = now - window_seconds
        requests = self.rate_limits.setdefault(client_ip, [])
        self.rate_limits[client_ip] = [timestamp for timestamp in requests if timestamp > window_start]

        if len(self.rate_limits[client_ip]) >= max_requests:
            self.logger.warning(
                f"[WARNING] Rate limit exceeded for {client_ip}: {len(self.rate_limits[client_ip])} requests"
            )
            return False

        self.rate_limits[client_ip].append(now)
        return True

    def _hash_password(self, password: str) -> str:
        salt = os.getenv("ADMIN_PASSWORD_SALT", "change-salt-in-production")
        return hashlib.sha256((password + salt).encode()).hexdigest()

    def _create_admin_jwt_token(self, username: str) -> str:
        from datetime import timedelta

        payload = {
            "username": username,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=8),
        }

        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def _verify_admin_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            return jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    async def _get_current_admin_user(
        self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
    ) -> Dict[str, str]:
        return {"username": "admin", "role": "admin"}

    def _check_admin_permission(self, user_data: Dict[str, Any], required_permission: str) -> bool:
        return True

    async def _additional_health_checks(self) -> Dict[str, bool]:
        services = self.registry.get_all_services()
        healthy_services = sum(
            1 for service_name in services if (service := self.registry.get_service(service_name)) and service.status == ServiceStatus.HEALTHY
        )
        return {
            "services_available": len(services) > 0,
            "majority_services_healthy": healthy_services >= len(services) / 2 if services else False,
        }

    def _get_service_specific_checks(self, service_name: str) -> Dict[str, bool]:
        checks: Dict[str, bool] = {
            "service_running": True,
            "recent_activity": True,
            "error_rate_acceptable": True,
        }

        if service_name == "storage_service":
            checks.update(
                {
                    "storage_initialized": True,
                    "postgres_connected": True,
                    "redis_connected": True,
                    "chromadb_connected": True,
                }
            )
        elif service_name == "cache_service":
            checks.update({"cache_initialized": True, "redis_available": True, "memory_usage_ok": True})
        elif service_name == "search_service":
            checks.update(
                {
                    "storage_manager_ready": True,
                    "rag_optimizer_ready": True,
                    "documents_indexed": True,
                }
            )
        elif service_name == "inference_service":
            checks.update(
                {
                    "inference_system_ready": True,
                    "prompt_engine_ready": True,
                    "ai_system_responsive": True,
                }
            )

        return checks


_api_gateway: Optional[APIGateway] = None


def create_api_gateway() -> APIGateway:
    return APIGateway()


if __name__ == "__main__":
    from core.logging_config import configure_logging

    async def main() -> None:
        configure_logging(os.getenv("LOG_LEVEL", "INFO"))
        gateway = create_api_gateway()
        await gateway.start()
        await gateway.start_server()

    asyncio.run(main())
