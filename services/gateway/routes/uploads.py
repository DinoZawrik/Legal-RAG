"""Загрузка и обработка документов."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from typing import Optional, TYPE_CHECKING

from fastapi import File, Form, HTTPException, Request, UploadFile

if TYPE_CHECKING:  # pragma: no cover
    from services.gateway.app import APIGateway


def register(gateway: "APIGateway") -> None:
    app = gateway.app

    @app.post("/api/upload")
    async def upload_document(
        file_path: Optional[str] = Form(None),
        file: Optional[UploadFile] = File(None),
        original_filename: str = Form(...),
        document_type: str = Form("regulatory"),
        is_presentation: str = Form("false"),
        presentation_supplement: str = Form("false"),
        contextual_extraction: str = Form("false"),
        force_reprocess: str = Form("false"),
        async_processing: str = Form("false"),
        http_request: Request = None,
    ):
        try:
            if not file_path and not file:
                raise HTTPException(status_code=422, detail="Either file_path or file must be provided")

            client_ip = http_request.client.host
            if not await gateway._check_rate_limit(client_ip):
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            request_id = uuid.uuid4().hex[:8]

            if file:
                filename = file.filename or original_filename
                file_extension = os.path.splitext(filename)[1] if filename else ".pdf"
                temp_dir = tempfile.gettempdir()

                safe_filename = "".join(c for c in filename if c.isalnum() or c in ("_", "-", ".", " "))
                base_name = os.path.splitext(safe_filename)[0] or "document"
                temp_filename = f"{base_name}_{uuid.uuid4().hex[:8]}{file_extension}"
                actual_file_path = os.path.join(temp_dir, temp_filename)

                with open(actual_file_path, "wb") as tmp_file:
                    shutil.copyfileobj(file.file, tmp_file)

                if not os.path.exists(actual_file_path):
                    raise HTTPException(status_code=500, detail="Не удалось создать временный файл")
            else:
                actual_file_path = file_path

            is_presentation_bool = is_presentation.lower() == "true"
            presentation_supplement_bool = presentation_supplement.lower() == "true"
            async_processing_bool = async_processing.lower() == "true"
            contextual_extraction_bool = contextual_extraction.lower() == "true"
            force_reprocess_bool = force_reprocess.lower() == "true"

            storage_request = {
                "type": "process_document",
                "data": {
                    "file_path": actual_file_path,
                    "document_type": document_type,
                    "metadata": {
                        "original_filename": original_filename,
                        "is_presentation": is_presentation_bool,
                        "presentation_supplement": presentation_supplement_bool,
                        "contextual_extraction": contextual_extraction_bool,
                        "force_reprocess": force_reprocess_bool,
                    },
                },
                "request_id": request_id,
            }

            storage_service = gateway.registry.get_service("storage_service")
            if not storage_service:
                raise HTTPException(status_code=503, detail="Storage service not available")

            if async_processing_bool:
                from core.task_queue import get_task_queue, TaskPriority

                task_queue = await get_task_queue()
                task_data = {
                    "file_path": actual_file_path,
                    "original_filename": original_filename,
                    "document_type": document_type,
                    "is_presentation": is_presentation_bool,
                    "presentation_supplement": presentation_supplement_bool,
                    "contextual_extraction": contextual_extraction_bool,
                    "force_reprocess": force_reprocess_bool,
                }

                priority = TaskPriority.HIGH if is_presentation_bool else TaskPriority.NORMAL
                task_id = await task_queue.add_task(
                    task_type="document_processing",
                    data=task_data,
                    priority=priority,
                )

                return {
                    "success": True,
                    "task_id": task_id,
                    "message": "Document processing started in background",
                    "status": "pending",
                    "request_id": request_id,
                    "check_status_url": f"/api/tasks/{task_id}/status",
                }

            try:
                if file and not os.path.exists(actual_file_path):
                    raise HTTPException(status_code=500, detail="Временный файл был удалён до обработки")

                response = await storage_service.handle_request(storage_request)
            except Exception as exc:
                gateway.logger.error(f"[CROSS_MARK] Storage service error: {exc}")
                raise

            gateway.logger.info(f"[SEARCH] DEBUG GATEWAY: storage response = {response}")
            data = response.get("data", {}).get("data", {})

            return {
                "success": response.get("success", False),
                "document_id": data.get("document_id"),
                "duplicate": data.get("duplicate", False),
                "chunks_created": data.get("chunks_created", 0),
                "contextual_data": data.get("contextual_data", {}),
                "message": data.get("message"),
                "request_id": request_id,
            }
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Document upload error: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))
        finally:
            if file and "actual_file_path" in locals():
                gateway.logger.info(
                    f"[CLIPBOARD] Временный файл {actual_file_path} будет удален storage_service после обработки"
                )
