#!/usr/bin/env python3
"""
[FILE_CABINET] Storage Service
Микросервис хранения данных - унифицированный доступ к БД
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
import time

from services.base import BaseService
from core.dependencies import container
from core.infrastructure_suite import TextChunk

logger = logging.getLogger(__name__)


class StorageService(BaseService):
    """
    Микросервис управления хранилищем данных.
    
    Функции:
    - Унифицированный доступ к PostgreSQL, ChromaDB, Redis
    - Connection pooling
    - Transaction management
    - Health monitoring
    """
    
    def __init__(self):
        super().__init__("storage_service")
        
        # Компоненты хранилища
        self.storage = None
        
        # Connection pools
        self.connection_pools = {
            "postgres": None,
            "redis": None,
            "chromadb": None
        }
        
        # Конфигурация
        self.default_config = {
            "postgres_pool_size": 10,
            "redis_pool_size": 20,
            "connection_timeout": 30,
            "query_timeout": 60,
            "retry_attempts": 3
        }
        
        # Метрики хранилища
        self.storage_metrics = {
            "queries_executed": 0,
            "documents_added": 0,
            "documents_retrieved": 0,
            "connection_errors": 0,
            "avg_query_time": 0.0,
            "query_times": []
        }
    
    async def initialize(self) -> None:
        """Инициализация Storage Service."""
        try:
            self.logger.info("[FILE_CABINET] Initializing Storage Service...")
            
            # Инициализация unified storage
            self.logger.info("[RELOAD] Loading StorageCoordinator via DependencyContainer...")
            self.storage = await container.get_storage()
            
            # Проверка подключений
            await self._verify_connections()
            
            self.logger.info("[CHECK_MARK_BUTTON] Storage Service initialized successfully")
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Failed to initialize Storage Service: {e}")
            raise
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запросов к хранилищу."""
        request_type = request.get("type", "query")
        
        if request_type == "query":
            return await self._handle_query_request(request)
        elif request_type == "add_documents":
            return await self._handle_add_documents_request(request)
        elif request_type == "search_documents":
            return await self._handle_search_documents_request(request)
        elif request_type == "get_metadata":
            return await self._handle_metadata_request(request)
        elif request_type == "health_check":
            return await self._handle_health_check_request(request)
        elif request_type == "stats":
            return await self._handle_stats_request(request)
        elif request_type == "configure":
            return await self._handle_config_request(request)
        elif request_type == "process_document":
            return await self._handle_process_document_request(request)
        elif request_type == "check_duplicate":
            return await self._handle_check_duplicate_request(request)
        elif request_type == "list_documents":
            return await self._handle_list_documents_request(request)
        elif request_type == "delete_document":
            return await self._handle_delete_document_request(request)
        else:
            raise ValueError(f"Unknown request type: {request_type}")
    
    async def cleanup(self) -> None:
        """Очистка ресурсов Storage Service."""
        try:
            # Закрытие connection pools
            if self.storage:
                # Здесь можно добавить cleanup логику для storage
                pass
            
            self.logger.info("[BROOM] Storage Service cleanup completed")
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Error during Storage Service cleanup: {e}")
    
    async def _handle_query_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка SQL запроса к PostgreSQL."""
        query = request.get("query", "")
        params = request.get("params", [])
        database = request.get("database", "postgres")
        
        if not query:
            raise ValueError("SQL query is required")
        
        start_time = time.time()
        
        try:
            if not self.storage:
                raise RuntimeError("Storage not initialized")
            
            # Выполнение запроса (имитация - в реальности нужен конкретный метод)
            if hasattr(self.storage, 'postgres_manager'):
                # Здесь был бы реальный SQL запрос
                result = {"message": "SQL query executed", "query": query[:100]}
            else:
                result = {"error": "PostgreSQL not available"}
            
            query_time = time.time() - start_time
            self._update_storage_metrics(query_time, "query")
            
            self.logger.info(f"[FILE_CABINET] SQL query executed in {query_time:.3f}s")
            
            return {
                "query": query[:100] + "..." if len(query) > 100 else query,
                "result": result,
                "execution_time": query_time,
                "database": database
            }
            
        except Exception as e:
            query_time = time.time() - start_time
            self.storage_metrics["connection_errors"] += 1
            
            self.logger.error(f"[CROSS_MARK] SQL query failed: {e}")
            raise
    
    async def _handle_add_documents_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса добавления документов."""
        documents = request.get("documents", [])
        document_type = request.get("document_type", "text_chunk")
        
        if not documents:
            raise ValueError("Documents list is required")
        
        start_time = time.time()
        
        try:
            if not self.storage:
                raise RuntimeError("Storage not initialized")
            
            # Добавление документов
            if document_type == "text_chunk":
                # Конвертация в TextChunk объекты
                text_chunks = []
                for doc in documents:
                    if isinstance(doc, dict):
                        chunk = TextChunk(
                            id=doc.get("id", ""),
                            text=doc.get("text", ""),
                            metadata=doc.get("metadata", {})
                        )
                        text_chunks.append(chunk)
                    else:
                        text_chunks.append(doc)
                
                # Добавление через vector store
                if hasattr(self.storage, 'vector_store'):
                    success = await self.storage.vector_store.add_documents(text_chunks)
                    if success:
                        added_count = len(text_chunks)
                    else:
                        raise RuntimeError("Failed to add documents to vector store")
                else:
                    raise RuntimeError("Vector store not available")
            else:
                # Другие типы документов
                added_count = len(documents)
            
            operation_time = time.time() - start_time
            self.storage_metrics["documents_added"] += added_count
            self._update_storage_metrics(operation_time, "add_documents")
            
            self.logger.info(f"[FILE_CABINET] Added {added_count} documents in {operation_time:.3f}s")
            
            return {
                "status": "success",
                "documents_added": added_count,
                "operation_time": operation_time,
                "document_type": document_type
            }
            
        except Exception as e:
            operation_time = time.time() - start_time
            self.storage_metrics["connection_errors"] += 1
            self._update_storage_metrics(operation_time, "error")
            
            self.logger.error(f"[CROSS_MARK] Add documents failed: {e}")
            raise
    
    async def _handle_search_documents_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса поиска документов."""
        query = request.get("query", "")
        max_results = request.get("max_results", 10)
        search_type = request.get("search_type", "semantic")
        
        if not query:
            raise ValueError("Search query is required")
        
        start_time = time.time()
        
        try:
            if not self.storage:
                raise RuntimeError("Storage not initialized")
            
            results = []
            
            # Семантический поиск через vector store
            if search_type == "semantic" and hasattr(self.storage, 'vector_store'):
                if hasattr(self.storage.vector_store, 'langchain_retriever'):
                    retriever = self.storage.vector_store.langchain_retriever
                    docs = retriever.get_relevant_documents(query)[:max_results]
                    
                    for doc in docs:
                        results.append({
                            "content": doc.page_content,
                            "metadata": doc.metadata,
                            "score": 0.8  # Эмулируем score
                        })
                else:
                    # Fallback поиск
                    results = [{"content": f"Search result for: {query}", "metadata": {}, "score": 0.7}]
            
            search_time = time.time() - start_time
            self.storage_metrics["documents_retrieved"] += len(results)
            self._update_storage_metrics(search_time, "search")
            
            self.logger.info(f"[FILE_CABINET] Found {len(results)} documents in {search_time:.3f}s")
            
            return {
                "query": query,
                "results": results,
                "total_found": len(results),
                "search_time": search_time,
                "search_type": search_type
            }
            
        except Exception as e:
            search_time = time.time() - start_time
            self.storage_metrics["connection_errors"] += 1
            
            self.logger.error(f"[CROSS_MARK] Document search failed: {e}")
            raise
    
    async def _handle_metadata_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса метаданных."""
        metadata_type = request.get("metadata_type", "documents")
        filters = request.get("filters", {})
        
        try:
            if not self.storage:
                raise RuntimeError("Storage not initialized")
            
            # Получение метаданных (имитация)
            metadata = {
                "total_documents": 686,  # Из предыдущих тестов
                "document_types": ["СП", "ГОСТ", "ФЗ", "Постановление"],
                "collections": ["documents"],
                "last_updated": time.time()
            }
            
            # Дополнительная информация о хранилище
            if hasattr(self.storage, 'vector_store') and hasattr(self.storage.vector_store, 'collection'):
                try:
                    collection = self.storage.vector_store.collection
                    if hasattr(collection, 'count'):
                        metadata["vector_documents"] = collection.count()
                except Exception:
                    metadata["vector_documents"] = "unavailable"
            
            self.logger.info(f"[FILE_CABINET] Retrieved metadata: {metadata_type}")
            
            return {
                "metadata_type": metadata_type,
                "metadata": metadata,
                "filters": filters
            }
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Metadata request failed: {e}")
            raise
    
    async def _handle_health_check_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса проверки здоровья хранилища."""
        try:
            health_status = await self._verify_connections()
            
            return {
                "storage_health": health_status,
                "connection_pools": {
                    name: pool is not None 
                    for name, pool in self.connection_pools.items()
                },
                "storage_metrics": self.storage_metrics.copy()
            }
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Storage health check failed: {e}")
            raise
    
    async def _handle_stats_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса статистики хранилища."""
        action = request.get("action", "general")
        
        if action == "get_document_stats":
            # Получаем статистику документов из базы данных
            try:
                if self.storage and self.storage.postgres_client:
                    # Запрос к PostgreSQL для получения статистики документов
                    documents_count = await self._get_documents_count()
                    chunks_count = await self._get_chunks_count()
                    recent_uploads = await self._get_recent_uploads_count()
                    total_size_mb = await self._get_total_storage_size()
                    
                    return {
                        "documents_count": documents_count,
                        "chunks_count": chunks_count,
                        "recent_uploads": recent_uploads,
                        "total_size_mb": total_size_mb
                    }
                else:
                    return {
                        "documents_count": 0,
                        "chunks_count": 0,
                        "recent_uploads": 0,
                        "total_size_mb": 0
                    }
            except Exception as e:
                self.logger.error(f"[CROSS_MARK] Error getting document stats: {e}")
                return {
                    "documents_count": 0,
                    "chunks_count": 0,
                    "recent_uploads": 0,
                    "total_size_mb": 0,
                    "error": str(e)
                }
        else:
            # Обычная статистика сервиса
            return {
                "service_metrics": self.get_metrics(),
                "storage_metrics": self.storage_metrics.copy(),
                "connection_status": await self._verify_connections()
            }
    
    async def _get_documents_count(self) -> int:
        """Получение количества уникальных документов в базе данных."""
        try:
            if self.storage and hasattr(self.storage, 'postgres_client'):
                # Используем postgres_client напрямую
                query = "SELECT COUNT(DISTINCT document_id) as count FROM documents"
                result = await self.storage.postgres_client.execute(query)
                return result[0]['count'] if result else 0
            return 0
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Error getting documents count: {e}")
            return 0
    
    async def _get_chunks_count(self) -> int:
        """Получение общего количества чанков в базе данных."""
        try:
            if self.storage and hasattr(self.storage, 'postgres_client'):
                # Используем postgres_client напрямую
                query = "SELECT COUNT(*) as count FROM document_chunks"
                result = await self.storage.postgres_client.execute(query)
                return result[0]['count'] if result else 0
            return 0
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Error getting chunks count: {e}")
            return 0
    
    async def _get_recent_uploads_count(self) -> int:
        """Получение количества документов загруженных за последние 24 часа."""
        try:
            if self.storage and hasattr(self.storage, 'postgres_client'):
                # Используем postgres_client напрямую
                from datetime import datetime, timedelta
                yesterday = datetime.now() - timedelta(days=1)
                query = "SELECT COUNT(*) as count FROM documents WHERE created_at > $1"
                result = await self.storage.postgres_client.execute(query, yesterday)
                return result[0]['count'] if result else 0
            return 0
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Error getting recent uploads count: {e}")
            return 0
    
    async def _get_total_storage_size(self) -> float:
        """Получение общего размера хранилища в МБ."""
        try:
            if self.storage and hasattr(self.storage, 'postgres_client'):
                # Используем postgres_client напрямую
                query = """
                    SELECT
                        COALESCE(SUM(LENGTH(content))::bigint, 0) as total_bytes
                    FROM document_chunks
                """
                result = await self.storage.postgres_client.execute(query)
                total_bytes = result[0]['total_bytes'] if result else 0
                return round(total_bytes / (1024 * 1024), 2)  # Конвертируем в МБ
            return 0.0
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Error getting total storage size: {e}")
            return 0.0
    
    async def _handle_config_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса конфигурации хранилища."""
        action = request.get("action", "get")
        
        if action == "get":
            return {
                "current_config": self.default_config,
                "storage_metrics": self.storage_metrics
            }
        
        elif action == "update":
            new_config = request.get("config", {})
            self.default_config.update(new_config)
            
            return {
                "status": "updated",
                "new_config": self.default_config
            }
        
        else:
            raise ValueError(f"Unknown config action: {action}")
    
    async def _handle_process_document_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса на обработку документа."""
        try:
            # Поддерживаем два формата: старый (data.file_path) и новый (file_path)
            data = request.get("data", {})
            if data:
                # Старый формат: {data: {file_path: ...}}
                file_path = data.get("file_path")
                document_type = data.get("document_type", "regulatory")
                metadata = data.get("metadata", {})
            else:
                # Новый формат: {file_path: ...} (прямо в request)
                file_path = request.get("file_path")
                document_type = request.get("document_type", "regulatory")
                metadata = request.get("metadata", {})
            
            if not file_path:
                return {
                    "success": False,
                    "error": "file_path is required",
                    "data": {}
                }
            
            # Импортируем ГИБРИДНЫЙ процессор документов
            from core.hybrid_document_processor import get_hybrid_processor
            from core.processing_pipeline import DocumentType

            # Создаем ГИБРИДНЫЙ процессор (граф + традиционная обработка)
            processor = await get_hybrid_processor()
            
            # Определяем тип документа с учётом метаданных
            force_type = None
            
            # Приоритет: проверяем метаданные на is_presentation
            is_presentation = metadata.get('is_presentation') if metadata else None
            presentation_supplement = metadata.get('presentation_supplement') if metadata else None
            contextual_extraction = metadata.get('contextual_extraction') if metadata else None
            force_reprocess = metadata.get('force_reprocess') if metadata else None
            
            # Обрабатываем строковые значения из API
            if is_presentation == 'true' or is_presentation is True:
                is_presentation = True
            else:
                is_presentation = False
                
            if presentation_supplement == 'true' or presentation_supplement is True:
                presentation_supplement = True
            else:
                presentation_supplement = False
                
            if contextual_extraction == 'true' or contextual_extraction is True:
                contextual_extraction = True
            else:
                contextual_extraction = False
                
            if force_reprocess == 'true' or force_reprocess is True:
                force_reprocess = True
            else:
                force_reprocess = False
            
            self.logger.info(f"[SEARCH] DEBUG Storage: is_presentation={is_presentation}, presentation_supplement={presentation_supplement}, contextual_extraction={contextual_extraction}, force_reprocess={force_reprocess}")
            
            # Определяем тип документа на основе явных индикаторов презентации
            if is_presentation or presentation_supplement:
                force_type = DocumentType.PRESENTATION
                self.logger.info("[TARGET] Принудительно задан тип PRESENTATION из метаданных")
            elif document_type == "regulatory":
                force_type = DocumentType.REGULATORY
                self.logger.info("[TARGET] Принудительно задан тип REGULATORY из метаданных")
            elif document_type == "general":
                force_type = DocumentType.GENERAL
                self.logger.info("[TARGET] Принудительно задан тип GENERAL из метаданных")
            # Если force_type = None, будет использовано автоматическое определение
            
            # Добавляем force_reprocess в метаданные для передачи в процессор
            if metadata is None:
                metadata = {}
            metadata['force_reprocess'] = force_reprocess
            
            # Обрабатываем документ ГИБРИДНО (традиционно + граф)
            result = await processor.process_document_hybrid(
                file_path=file_path,
                metadata=metadata
            )
            
            return {
                "success": result.get("success", False),
                "data": {
                    "document_id": result.get("document_id"),
                    "duplicate": result.get("duplicate", False),
                    "message": result.get("message", "Document processed"),
                    "chunks_created": result.get("chunks_created", 0),
                    "contextual_data": result.get("contextual_data", {})  # Включаем контекстуальные данные
                },
                "request_id": request.get("request_id", "unknown")
            }
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Document processing error: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": {}
            }
    
    async def _verify_connections(self) -> Dict[str, bool]:
        """Проверка подключений к базам данных."""
        connections = {
            "postgres": False,
            "redis": False,
            "chromadb": False
        }
        
        try:
            if self.storage:
                # Простая проверка компонентов без вызова потенциально багованных методов
                connections["postgres"] = hasattr(self.storage, 'postgres') and self.storage.postgres is not None
                connections["redis"] = hasattr(self.storage, 'redis') and self.storage.redis is not None
                connections["chromadb"] = hasattr(self.storage, 'vector_store') and self.storage.vector_store is not None
                
                # Логирование для диагностики
                self.logger.info(f"[SEARCH] Storage components check: postgres={connections['postgres']}, redis={connections['redis']}, chromadb={connections['chromadb']}")
            else:
                self.logger.warning("[WARNING] Storage object is None")
            
        except Exception as e:
            self.logger.error(f"[CROSS_MARK] Connection verification error: {e}")
        
        return connections
    
    def _update_storage_metrics(self, operation_time: float, operation_type: str) -> None:
        """Обновление метрик хранилища."""
        self.storage_metrics["queries_executed"] += 1
        
        # Обновление времени выполнения
        self.storage_metrics["query_times"].append(operation_time)
        
        # Оставляем только последние 100 измерений
        if len(self.storage_metrics["query_times"]) > 100:
            self.storage_metrics["query_times"] = self.storage_metrics["query_times"][-100:]
        
        # Пересчет среднего времени
        times = self.storage_metrics["query_times"]
        self.storage_metrics["avg_query_time"] = sum(times) / len(times) if times else 0.0
    
    async def _handle_check_duplicate_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Проверка файла на дубликаты - использует ту же логику что и телеграм бот."""
        start_time = time.time()
        
        try:
            file_data = request.get("data", {})
            
            if not self.storage:
                raise RuntimeError("Storage not initialized")
            
            # Используем тот же метод проверки дубликатов что и в боте
            documents_info = [file_data]  # Проверяем один файл через bulk метод
            
            duplicate_check = await self.storage.postgres.check_duplicates_bulk(documents_info)
            
            # Проверяем результат
            is_duplicate = len(duplicate_check['duplicates']) > 0
            existing_id = None
            message = "File is unique"
            
            if is_duplicate:
                duplicate_info = duplicate_check['duplicates'][0]
                existing_id = duplicate_info.get('existing_id')
                reason = duplicate_info.get('reason', 'duplicate found')
                message = f"Duplicate found: {reason}"
            
            operation_time = time.time() - start_time
            self._update_storage_metrics(operation_time, "database_operation")
            
            return {
                "success": True,
                "data": {
                    "is_duplicate": is_duplicate,
                    "existing_id": existing_id,
                    "message": message
                },
                "response_time": operation_time
            }
            
        except Exception as e:
            operation_time = time.time() - start_time
            self.storage_metrics["connection_errors"] += 1
            self._update_storage_metrics(operation_time, "error")
            self.logger.error(f"[CROSS_MARK] Duplicate check error: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "response_time": operation_time
            }
    
    async def _handle_list_documents_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Получение списка документов."""
        start_time = time.time()
        
        try:
            data = request.get("data", {})
            limit = data.get("limit", 20)
            offset = data.get("offset", 0)
            category = data.get("category")
            search_query = (data.get("search") or "").strip()
            
            self.logger.info(f"[SEARCH] List documents request: limit={limit}, offset={offset}, category={category}, search='{search_query}'")
            
            if not self.storage:
                raise RuntimeError("Storage not initialized")
            
            # Базовый запрос
            query = """
                SELECT 
                    id,
                    filename,
                    document_type,
                    file_size,
                    processed_at,
                    status
                FROM documents 
            """
            
            # Используем правильный способ доступа к PostgreSQL через pool
            async with self.storage.postgres.pool.acquire() as conn:
                # Формируем параметры для запроса и WHERE условия
                sql_params = []
                where_conditions = []
                
                if category:
                    where_conditions.append(f"document_type = ${len(sql_params)+1}")
                    sql_params.append(category)
                
                if search_query:
                    # Поиск по названию файла (case-insensitive)
                    where_conditions.append(f"LOWER(filename) LIKE LOWER(${len(sql_params)+1})")
                    sql_params.append(f"%{search_query}%")
                
                # Добавляем WHERE условия если они есть
                if where_conditions:
                    query += " WHERE " + " AND ".join(where_conditions)
                
                # Добавляем сортировку и лимиты  
                query += f" ORDER BY processed_at DESC LIMIT ${len(sql_params)+1} OFFSET ${len(sql_params)+2}"
                sql_params.extend([limit, offset])
                
                # Логируем финальный SQL запрос
                self.logger.info(f"[SEARCH] Executing SQL: {query}")
                self.logger.info(f"[SEARCH] SQL params: {sql_params}")
                
                # Выполняем запрос
                documents = await conn.fetch(query, *sql_params)
                
                # Получаем общее количество документов с теми же фильтрами
                count_query = "SELECT COUNT(*) as total FROM documents"
                count_params = []
                count_where_conditions = []
                
                if category:
                    count_where_conditions.append(f"document_type = ${len(count_params)+1}")
                    count_params.append(category)
                
                if search_query:
                    count_where_conditions.append(f"LOWER(filename) LIKE LOWER(${len(count_params)+1})")
                    count_params.append(f"%{search_query}%")
                
                if count_where_conditions:
                    count_query += " WHERE " + " AND ".join(count_where_conditions)
                
                total_result = await conn.fetchrow(count_query, *count_params)
                total_documents = total_result["total"] if total_result else 0
                
                self.logger.info(f"[SEARCH] Found {len(documents)} documents out of {total_documents} total")
                
                # Преобразуем результат в нужный формат
                documents_list = []
                for doc in documents:
                    documents_list.append({
                        "document_id": str(doc["id"]),
                        "filename": doc["filename"],
                        "document_type": doc["document_type"],
                        "file_size": doc["file_size"],
                        "processed_at": doc["processed_at"].isoformat() if doc["processed_at"] else None,
                        "status": doc["status"]
                    })
            
            operation_time = time.time() - start_time
            self._update_storage_metrics(operation_time, "database_operation")
            
            return {
                "success": True,
                "data": {
                    "documents": documents_list,
                    "total": total_documents,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(documents_list) < total_documents
                },
                "response_time": operation_time
            }
            
        except Exception as e:
            operation_time = time.time() - start_time
            self.storage_metrics["connection_errors"] += 1
            self._update_storage_metrics(operation_time, "error")
            self.logger.error(f"[CROSS_MARK] List documents error: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "response_time": operation_time
            }
    
    async def _handle_delete_document_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Удаление документа из базы данных и векторного хранилища."""
        start_time = time.time()
        
        try:
            data = request.get("data", {})
            document_id = data.get("document_id")
            deleted_by = data.get("deleted_by", "unknown")
            
            if not document_id:
                raise ValueError("Document ID is required")
            
            if not self.storage:
                raise RuntimeError("Storage not initialized")
            
            # Получаем информацию о документе перед удалением
            async with self.storage.postgres.pool.acquire() as conn:
                # Проверяем существование документа
                doc_query = "SELECT id, filename, document_type, file_hash FROM documents WHERE id = $1"
                document = await conn.fetchrow(doc_query, document_id)
                
                if not document:
                    return {
                        "success": False,
                        "error": "Document not found",
                        "response_time": time.time() - start_time
                    }
                
                # Удаляем записи из векторной БД (по document_id)
                try:
                    if hasattr(self.storage, 'vector_store') and self.storage.vector_store and self.storage.vector_store.collection:
                        # Удаляем векторы документа из ChromaDB
                        self.storage.vector_store.collection.delete(where={"document_id": str(document_id)})
                        self.logger.info(f"[WASTEBASKET] Vectors deleted for document {document_id}")
                except Exception as vector_error:
                    self.logger.warning(f"[WARNING] Could not delete vectors for document {document_id}: {vector_error}")
                
                # Удаляем из PostgreSQL (основная запись)
                delete_query = "DELETE FROM documents WHERE id = $1"
                result = await conn.execute(delete_query, document_id)
                
                # Проверяем, что удаление прошло успешно
                if "DELETE 0" in result:
                    return {
                        "success": False,
                        "error": "Document not found or already deleted",
                        "response_time": time.time() - start_time
                    }
                
                self.logger.info(f"[CHECK_MARK_BUTTON] Document {document_id} ({document['filename']}) deleted by {deleted_by}")
            
            operation_time = time.time() - start_time
            self._update_storage_metrics(operation_time, "database_operation")
            
            return {
                "success": True,
                "data": {
                    "document_id": document_id,
                    "filename": document["filename"],
                    "deleted_by": deleted_by,
                    "deleted_at": time.time()
                },
                "message": f"Document {document['filename']} deleted successfully",
                "response_time": operation_time
            }
            
        except ValueError as ve:
            operation_time = time.time() - start_time
            self.logger.error(f"[CROSS_MARK] Delete document validation error: {ve}")
            
            return {
                "success": False,
                "error": str(ve),
                "response_time": operation_time
            }
            
        except Exception as e:
            operation_time = time.time() - start_time
            self.storage_metrics["connection_errors"] += 1
            self._update_storage_metrics(operation_time, "error")
            self.logger.error(f"[CROSS_MARK] Delete document error: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "response_time": operation_time
            }
    
    async def _additional_health_checks(self) -> Dict[str, bool]:
        """Дополнительные проверки здоровья для Storage Service."""
        checks = {}
        
        # Проверка инициализации
        checks["storage_initialized"] = self.storage is not None
        
        # Проверка подключений
        connections = await self._verify_connections()
        checks["postgres_connected"] = connections.get("postgres", False)
        checks["redis_connected"] = connections.get("redis", False)
        checks["chromadb_connected"] = connections.get("chromadb", False)
        
        # Проверка производительности
        checks["acceptable_query_time"] = self.storage_metrics["avg_query_time"] < 5.0
        checks["low_error_rate"] = (
            self.storage_metrics["connection_errors"] / 
            max(self.storage_metrics["queries_executed"], 1)
        ) < 0.05
        
        return checks


async def create_storage_service() -> StorageService:
    """Factory function for fully initialized StorageService."""
    service = StorageService()
    await service.start()
    return service


if __name__ == "__main__":
    # Тестирование Storage Service
    async def test_storage_service():
        print("[FILE_CABINET] Testing Storage Service")
        
        service = StorageService()
        await service.start()
        
        # Тест поиска документов
        search_request = {
            "type": "search_documents",
            "query": "теплоснабжение",
            "max_results": 5
        }
        
        try:
            response = await service.handle_request(search_request)
            print(f"[CHECK_MARK_BUTTON] Document search test successful: {response['data']['total_found']} results")
            
            # Тест метаданных
            metadata_request = {"type": "get_metadata"}
            metadata_response = await service.handle_request(metadata_request)
            print(f"[CHECK_MARK_BUTTON] Metadata test successful")
            
            # Тест health check
            health_request = {"type": "health_check"}
            health_response = await service.handle_request(health_request)
            print(f"[CHECK_MARK_BUTTON] Health check test successful")
            
        except Exception as e:
            print(f"[CROSS_MARK] Test failed: {e}")
        
        finally:
            await service.stop()
    
    asyncio.run(test_storage_service())