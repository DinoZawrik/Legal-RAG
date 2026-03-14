#!/usr/bin/env python3
"""
Document Processing Worker
Background worker для обработки документов через Task Queue
"""

import asyncio
import logging
import os
import tempfile
import aiohttp
from typing import Dict, Any
from pathlib import Path

from core.task_queue import TaskQueue, Task

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Worker для обработки документов в фоновом режиме.
    """
    
    def __init__(self, microservices_url: str = None):
        self.task_queue = TaskQueue()
        # Используем внутренний Docker URL для микросервисов
        self.microservices_url = microservices_url or os.getenv(
            "MICROSERVICES_URL",
            "http://legalrag_microservices:8080"
        )
        
    async def initialize(self):
        """Инициализация worker'а."""
        await self.task_queue.connect()
        
        # Регистрируем обработчики
        self.task_queue.register_handler("document_processing", self.process_document)
        self.task_queue.register_handler("document_upload", self.process_document_upload)
        
        logger.info(" DocumentProcessor initialized")
    
    async def _call_microservice(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Вызов микросервиса через HTTP API."""
        url = f"{self.microservices_url}{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status != 200:
                    raise RuntimeError(f"Microservice error: {response.status}")
                return await response.json()
    
    async def process_document(self, task: Task) -> Dict[str, Any]:
        """
        Обработка документа.
        
        Args:
            task: Задача с данными для обработки
            
        Returns:
            Dict с результатами обработки
        """
        try:
            data = task.data
            file_path = data.get("file_path")
            original_filename = data.get("original_filename", "document.pdf")
            document_type = data.get("document_type", "regulatory")
            is_presentation = data.get("is_presentation", False)
            presentation_supplement = data.get("presentation_supplement", False)
            contextual_extraction = data.get("contextual_extraction", False)
            force_reprocess = data.get("force_reprocess", False)
            
            if not file_path:
                raise ValueError("file_path is required")
            
            # Обновляем прогресс
            await self.task_queue.update_progress(task.task_id, 10, "Initializing document processing")
            
            # Подготавливаем запрос для microservice
            storage_request = {
                "file_path": file_path,
                "original_filename": original_filename,
                "document_type": document_type,
                "metadata": {
                    "is_presentation": is_presentation,
                    "presentation_supplement": presentation_supplement,
                    "contextual_extraction": contextual_extraction,
                    "force_reprocess": force_reprocess
                },
                "request_id": task.task_id
            }
            
            # Обновляем прогресс
            await self.task_queue.update_progress(task.task_id, 25, "Starting document processing")
            
            # Вызываем storage service через HTTP API
            service_request = {
                "service": "storage_service",
                "action": "process_document", 
                "data": storage_request
            }
            response = await self._call_microservice("/api/service/storage_service", service_request)
            
            # Проверяем успешность
            if not response.get("success"):
                error_msg = response.get("error", "Unknown error during processing")
                raise RuntimeError(f"Document processing failed: {error_msg}")
            
            # Извлекаем данные результата
            result_data = response.get("data", {}).get("data", {})
            
            # Обновляем прогресс
            await self.task_queue.update_progress(task.task_id, 90, "Document processing completed")
            
            # Формируем результат
            result = {
                "success": True,
                "document_id": result_data.get("document_id"),
                "duplicate": result_data.get("duplicate", False),
                "chunks_created": result_data.get("chunks_created", 0),
                "contextual_data": result_data.get("contextual_data", {}),
                "message": result_data.get("message", "Document processed successfully"),
                "processing_time": result_data.get("processing_time", 0),
                "original_filename": original_filename
            }
            
            # Финальное обновление прогресса
            await self.task_queue.update_progress(task.task_id, 100, "Task completed successfully")
            
            logger.info(f" Document processing completed for task {task.task_id}")
            return result
            
        except Exception as e:
            logger.error(f" Document processing failed for task {task.task_id}: {e}")
            await self.task_queue.update_progress(task.task_id, 0, f"Error: {str(e)}")
            raise
    
    async def process_document_upload(self, task: Task) -> Dict[str, Any]:
        """
        Обработка загрузки документа с временным файлом.
        
        Args:
            task: Задача с данными для обработки
            
        Returns:
            Dict с результатами обработки
        """
        temp_file_path = None
        try:
            data = task.data
            file_content = data.get("file_content")
            original_filename = data.get("original_filename", "document.pdf")
            document_type = data.get("document_type", "regulatory")
            is_presentation = data.get("is_presentation", False)
            presentation_supplement = data.get("presentation_supplement", False)
            contextual_extraction = data.get("contextual_extraction", False)
            force_reprocess = data.get("force_reprocess", False)
            
            if not file_content:
                raise ValueError("file_content is required")
            
            # Обновляем прогресс
            await self.task_queue.update_progress(task.task_id, 5, "Creating temporary file")
            
            # Создаем временный файл
            file_extension = Path(original_filename).suffix or '.pdf'
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                if isinstance(file_content, str):
                    # Декодируем base64 если нужно
                    import base64
                    try:
                        file_bytes = base64.b64decode(file_content)
                        tmp_file.write(file_bytes)
                    except Exception:
                        # Возможно, это уже байты
                        tmp_file.write(file_content.encode())
                else:
                    tmp_file.write(file_content)
                
                temp_file_path = tmp_file.name
            
            # Обновляем данные задачи для обработки
            task.data.update({
                "file_path": temp_file_path,
                "original_filename": original_filename,
                "document_type": document_type,
                "is_presentation": is_presentation,
                "presentation_supplement": presentation_supplement,
                "contextual_extraction": contextual_extraction,
                "force_reprocess": force_reprocess
            })
            
            # Удаляем file_content чтобы не передавать большие данные дальше
            del task.data["file_content"]
            
            # Обрабатываем как обычный документ
            result = await self.process_document(task)
            
            return result
            
        except Exception as e:
            logger.error(f" Document upload processing failed for task {task.task_id}: {e}")
            await self.task_queue.update_progress(task.task_id, 0, f"Error: {str(e)}")
            raise
        finally:
            # Удаляем временный файл
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    logger.debug(f" Temporary file {temp_file_path} deleted")
                except Exception as e:
                    logger.warning(f" Failed to delete temporary file {temp_file_path}: {e}")
    
    async def start_worker(self, worker_id: str = None):
        """Запуск worker'а для обработки задач."""
        await self.initialize()
        await self.task_queue.process_tasks(worker_id)
    
    async def shutdown(self):
        """Завершение работы worker'а."""
        await self.task_queue.disconnect()
        logger.info(" DocumentProcessor shutdown completed")


async def start_document_worker(worker_id: str = None):
    """
    Функция для запуска document worker'а.
    Может использоваться как отдельный процесс.
    """
    processor = DocumentProcessor()
    
    try:
        await processor.start_worker(worker_id)
    except KeyboardInterrupt:
        logger.info(" Worker interrupted by user")
    except Exception as e:
        logger.error(f" Worker failed: {e}")
    finally:
        await processor.shutdown()


if __name__ == "__main__":
    from core.logging_config import configure_logging

    configure_logging()

    # Запуск worker'а
    asyncio.run(start_document_worker("main-worker"))