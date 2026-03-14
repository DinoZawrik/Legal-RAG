"""Административные endpoints API Gateway."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from core.user_management import PermissionType, TelegramUser, UserStatus, user_manager
from services.base import ServiceStatus
from services.gateway.models import AdminFileUpload, AdminLoginRequest

if TYPE_CHECKING:  # pragma: no cover
    from services.gateway.app import APIGateway


def register(gateway: "APIGateway") -> None:
    app = gateway.app
    _register_auth_routes(app, gateway)
    _register_system_metrics_route(app, gateway)
    _register_file_routes(app, gateway)
    _register_user_routes(app, gateway)
    _register_logs_route(app, gateway)
    _register_rag_config_route(app, gateway)
    _register_document_stats_route(app, gateway)
    _register_telegram_routes(app, gateway)


def _register_auth_routes(app, gateway: "APIGateway") -> None:
    @app.post("/admin/auth/login")
    async def admin_login(request: AdminLoginRequest):
        try:
            if request.password != gateway.admin_password:
                raise HTTPException(status_code=401, detail="Invalid credentials")

            token = gateway._create_admin_jwt_token("admin")
            return {
                "access_token": token,
                "token_type": "bearer",
                "username": "admin",
                "role": "admin",
            }
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Admin login error: {exc}")
            raise HTTPException(status_code=500, detail="Login failed")


def _register_system_metrics_route(app, gateway: "APIGateway") -> None:
    @app.get("/admin/metrics/system")
    async def admin_get_system_metrics(admin_user=Depends(gateway._get_current_admin_user)):
        if not gateway._check_admin_permission(admin_user, "dashboard"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        try:
            metrics = {
                "gateway": gateway.get_metrics(),
                "services": {},
                "system": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "uptime": gateway.metrics.uptime_seconds,
                    "total_requests": gateway.metrics.request_count,
                },
            }

            for service_name in gateway.registry.get_all_services():
                service = gateway.registry.get_service(service_name)
                if service:
                    service_metrics = service.get_metrics()
                    metrics["services"][service_name] = {
                        **service_metrics,
                        "status": service.status.value,
                        "service_id": service.service_id,
                    }

            health_checks = await gateway.registry.get_all_health_checks()
            metrics["health_summary"] = {
                "total_services": len(health_checks),
                "healthy_services": sum(1 for health in health_checks.values() if health.status == ServiceStatus.HEALTHY),
                "details": {name: health.to_dict() for name, health in health_checks.items()},
            }

            return metrics
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Error getting system metrics: {exc}")
            raise HTTPException(status_code=500, detail="Failed to get system metrics")


def _register_file_routes(app, gateway: "APIGateway") -> None:
    @app.post("/admin/files/upload")
    async def admin_upload_files(
        files: List[UploadFile] = File(...),
        category: str = Form("general"),
        auto_process: bool = Form(True),
        skip_duplicates: bool = Form(True),
        document_type: str = Form("general"),
        is_presentation: bool = Form(False),
        contextual_extraction: bool = Form(False),
        presentation_supplement: bool = Form(False),
        admin_user=Depends(gateway._get_current_admin_user),
    ):
        if not gateway._check_admin_permission(admin_user, "files"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        try:
            results: List[Dict[str, Any]] = []
            total_files = len(files)
            uploaded_count = 0
            skipped_count = 0
            error_count = 0

            storage_service = gateway.registry.get_service("storage_service")
            if not storage_service:
                raise HTTPException(status_code=503, detail="Storage service unavailable")

            for file in files:
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp_file:
                        shutil.copyfileobj(file.file, tmp_file)
                        tmp_file_path = tmp_file.name

                    storage_request = {
                        "type": "process_document",
                        "data": {
                            "file_path": tmp_file_path,
                            "document_type": document_type,
                            "category": category,
                            "metadata": {
                                "original_filename": file.filename,
                                "uploaded_by": admin_user["username"],
                                "is_presentation": is_presentation,
                                "contextual_extraction": contextual_extraction,
                                "presentation_supplement": presentation_supplement,
                            },
                        },
                        "request_id": uuid.uuid4().hex[:8],
                    }

                    response = await storage_service.handle_request(storage_request)

                    try:
                        os.unlink(tmp_file_path)
                    except Exception:  # pragma: no cover
                        pass

                    if response.get("success"):
                        data = response.get("data", {}).get("data", {})
                        if data.get("duplicate") and skip_duplicates:
                            skipped_count += 1
                            results.append(
                                {
                                    "filename": file.filename,
                                    "status": "skipped",
                                    "message": "Duplicate file skipped",
                                    "document_id": data.get("document_id"),
                                }
                            )
                        else:
                            uploaded_count += 1
                            results.append(
                                {
                                    "filename": file.filename,
                                    "status": "success",
                                    "message": "File uploaded successfully",
                                    "document_id": data.get("document_id"),
                                    "chunks_created": data.get("chunks_created", 0),
                                }
                            )
                    else:
                        error_count += 1
                        results.append(
                            {
                                "filename": file.filename,
                                "status": "error",
                                "message": response.get("error", "Unknown error"),
                            }
                        )
                except Exception as file_error:
                    error_count += 1
                    results.append({"filename": file.filename, "status": "error", "message": str(file_error)})

            return {
                "success": True,
                "summary": {
                    "total_files": total_files,
                    "uploaded": uploaded_count,
                    "skipped": skipped_count,
                    "errors": error_count,
                },
                "results": results,
                "uploaded_by": admin_user["username"],
            }
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Admin file upload error: {exc}")
            raise HTTPException(status_code=500, detail="File upload failed")

    @app.post("/admin/files/check-duplicate")
    async def admin_check_duplicate(file_data: Dict[str, Any], admin_user=Depends(gateway._get_current_admin_user)):
        if not gateway._check_admin_permission(admin_user, "files"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        try:
            storage_service = gateway.registry.get_service("storage_service")
            if not storage_service:
                raise HTTPException(status_code=503, detail="Storage service unavailable")

            storage_request = {
                "type": "check_duplicate",
                "data": file_data,
                "request_id": uuid.uuid4().hex[:8],
            }

            response = await storage_service.handle_request(storage_request)

            if response.get("success"):
                return {
                    "is_duplicate": response.get("data", {}).get("is_duplicate", False),
                    "existing_id": response.get("data", {}).get("existing_id"),
                    "message": response.get("data", {}).get("message", ""),
                }

            return {"is_duplicate": False, "message": "Could not check for duplicates"}
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Duplicate check error: {exc}")
            return {"is_duplicate": False, "message": f"Error checking duplicates: {str(exc)}"}

    @app.get("/admin/files/list")
    async def admin_list_files(
        limit: int = 20,
        offset: int = 0,
        category: Optional[str] = None,
        search: Optional[str] = None,
        admin_user=Depends(gateway._get_current_admin_user),
    ):
        if not gateway._check_admin_permission(admin_user, "files"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        try:
            storage_service = gateway.registry.get_service("storage_service")
            if not storage_service:
                raise HTTPException(status_code=503, detail="Storage service unavailable")

            storage_request = {
                "type": "list_documents",
                "data": {
                    "limit": limit,
                    "offset": offset,
                    "category": category,
                    "search": search,
                },
                "request_id": uuid.uuid4().hex[:8],
            }

            response = await storage_service.handle_request(storage_request)
            if response.get("success"):
                return response.get("data", {})
            raise HTTPException(status_code=500, detail=response.get("error", "Failed to list files"))
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] List files error: {exc}")
            raise HTTPException(status_code=500, detail="Failed to list files")

    @app.delete("/admin/files/{doc_id}")
    async def admin_delete_file(doc_id: str, admin_user=Depends(gateway._get_current_admin_user)):
        if not gateway._check_admin_permission(admin_user, "files"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        try:
            storage_service = gateway.registry.get_service("storage_service")
            if not storage_service:
                raise HTTPException(status_code=503, detail="Storage service unavailable")

            storage_request = {
                "type": "delete_document",
                "data": {"document_id": doc_id, "deleted_by": admin_user["username"]},
                "request_id": uuid.uuid4().hex[:8],
            }

            response = await storage_service.handle_request(storage_request)

            if response.get("success"):
                gateway.logger.info(
                    f"[CHECK_MARK_BUTTON] File deleted successfully: {doc_id} by {admin_user['username']}"
                )
                return {
                    "success": True,
                    "message": f"File {doc_id} deleted successfully",
                    "deleted_by": admin_user["username"],
                }

            if response.get("error") == "Document not found":
                raise HTTPException(status_code=404, detail="File not found")

            raise HTTPException(status_code=500, detail=response.get("error", "Failed to delete file"))
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Delete file error: {exc}")
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(exc)}")


def _register_user_routes(app, gateway: "APIGateway") -> None:
    @app.get("/admin/users/list")
    async def admin_get_users(admin_user=Depends(gateway._get_current_admin_user)):
        if not gateway._check_admin_permission(admin_user, "users"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        users = [
            {
                "user_id": 1,
                "username": "admin",
                "telegram_id": 123456789,
                "role": "super_admin",
                "status": "active",
                "last_activity": "2024-08-20T10:30:00Z",
                "created_at": "2024-01-01T00:00:00Z",
                "requests_count": 1250,
            }
        ]

        return {"users": users, "total_count": len(users), "requested_by": admin_user["username"]}


def _register_logs_route(app, gateway: "APIGateway") -> None:
    @app.get("/admin/logs/stream")
    async def admin_get_logs(level: str = "INFO", limit: int = 100, admin_user=Depends(gateway._get_current_admin_user)):
        if not gateway._check_admin_permission(admin_user, "logs"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        logs = [
            {
                "timestamp": "2024-08-20T10:30:00Z",
                "level": "INFO",
                "service": "api_gateway",
                "message": "System started successfully",
                "request_id": "abc12345",
            },
            {
                "timestamp": "2024-08-20T10:25:00Z",
                "level": "INFO",
                "service": "storage_service",
                "message": "5 new documents processed",
                "request_id": "def67890",
            },
        ]

        if level != "ALL":
            logs = [log for log in logs if log["level"] == level]

        return {
            "logs": logs[:limit],
            "total_count": min(len(logs), limit),
            "level_filter": level,
            "requested_by": admin_user["username"],
        }


def _register_rag_config_route(app, gateway: "APIGateway") -> None:
    @app.get("/admin/config/rag")
    async def admin_get_rag_config(admin_user=Depends(gateway._get_current_admin_user)):
        if not gateway._check_admin_permission(admin_user, "settings"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        try:
            from pathlib import Path

            config_path = Path("rag_configs.json")
            if config_path.exists():
                with config_path.open("r", encoding="utf-8") as file:
                    rag_configs = json.load(file)
            else:
                rag_configs = {}

            return {
                "configs": rag_configs,
                "current_config": os.getenv("RAG_CONFIG_NAME", "optimal"),
                "requested_by": admin_user["username"],
            }
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Error getting RAG config: {exc}")
            raise HTTPException(status_code=500, detail="Failed to get RAG config")


def _register_document_stats_route(app, gateway: "APIGateway") -> None:
    @app.get("/admin/stats/documents")
    async def admin_get_document_stats(admin_user=Depends(gateway._get_current_admin_user)):
        try:
            storage_service = gateway.registry.get_service("storage_service")
            if not storage_service:
                raise HTTPException(status_code=503, detail="Storage service unavailable")

            stats_request = {
                "type": "stats",
                "action": "get_document_stats",
                "data": {},
                "request_id": uuid.uuid4().hex[:8],
            }

            stats_response = await storage_service.handle_request(stats_request)

            if stats_response.get("success"):
                return {
                    "success": True,
                    "data": stats_response.get("data", {}),
                    "requested_by": admin_user["username"],
                }

            return {
                "success": False,
                "data": {
                    "documents_count": 0,
                    "chunks_count": 0,
                    "recent_uploads": 0,
                    "total_size_mb": 0,
                },
                "error": stats_response.get("error", "Unknown error"),
                "requested_by": admin_user["username"],
            }
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Error getting document stats: {exc}")
            return {
                "success": False,
                "data": {
                    "documents_count": 0,
                    "chunks_count": 0,
                    "recent_uploads": 0,
                    "total_size_mb": 0,
                },
                "error": str(exc),
                "requested_by": admin_user["username"],
            }


def _register_telegram_routes(app, gateway: "APIGateway") -> None:
    @app.get("/admin/telegram-users/list")
    async def admin_get_telegram_users(admin_user=Depends(gateway._get_current_admin_user)):
        try:
            users = await user_manager.get_all_users(limit=100, offset=0)
            telegram_users = [user.to_dict() for user in users]
            admin_ids = await user_manager.get_users_with_upload_permission()

            return {
                "telegram_users": telegram_users,
                "total_count": len(telegram_users),
                "current_admin_ids": admin_ids,
                "requested_by": admin_user["username"],
            }
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Error getting Telegram users: {exc}")
            raise HTTPException(status_code=500, detail="Failed to get Telegram users")

    @app.post("/admin/telegram-users/add")
    async def admin_add_telegram_user(user_data: Dict[str, Any], admin_user=Depends(gateway._get_current_admin_user)):
        try:
            telegram_id = user_data.get("telegram_id")
            first_name = user_data.get("first_name", f"Пользователь {telegram_id}")
            username = user_data.get("username")
            permissions = user_data.get("permissions", "upload_documents")
            comment = user_data.get("comment", "")

            if not telegram_id or not isinstance(telegram_id, int):
                raise HTTPException(status_code=400, detail="Invalid telegram_id")

            existing_user = await user_manager.get_user_by_telegram_id(telegram_id)
            if existing_user:
                raise HTTPException(status_code=400, detail=f"User {telegram_id} already exists")

            user_permissions: List[str] = []
            if permissions == "upload_documents":
                user_permissions.append(PermissionType.UPLOAD_DOCUMENTS.value)

            new_user = TelegramUser(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                status=UserStatus.ACTIVE,
                comment=comment,
                permissions=user_permissions,
            )

            created_user = await user_manager.create_user(new_user, admin_user["username"])
            if not created_user:
                raise HTTPException(status_code=500, detail="Failed to create user")

            gateway.logger.info(
                f"[CHECK_MARK_BUTTON] Добавлен Telegram пользователь {telegram_id} с правами {permissions}"
            )

            return {
                "success": True,
                "message": f"Пользователь {telegram_id} добавлен",
                "user": created_user.to_dict(),
                "added_by": admin_user["username"],
            }
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Error adding Telegram user: {exc}")
            raise HTTPException(status_code=500, detail="Failed to add Telegram user")
