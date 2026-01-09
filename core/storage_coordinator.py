"""Centralized storage coordinator combining Postgres, Redis and Vector Store."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.infrastructure_suite import TextChunk
from core.postgres_manager import PostgresManager
from core.redis_manager import RedisManager
from core.vector_store_manager import VectorStoreManager
from core.pgvector_manager import PgVectorManager

logger = logging.getLogger(__name__)


class StorageCoordinator:
    """Coordinate access to Postgres, Redis and Vector Store."""

    def __init__(
        self,
        postgres: Optional[PostgresManager] = None,
        redis: Optional[RedisManager] = None,
        vector_store: Optional[VectorStoreManager] = None,
        use_pgvector: bool = False,  # Новая опция для переключения на pgvector
    ) -> None:
        self.postgres = postgres or PostgresManager()
        self.redis = redis or RedisManager()
        self.use_pgvector = use_pgvector
        
        if use_pgvector:
            # Используем pgvector как векторное хранилище
            self.vector_store = None  # PgVectorManager использует postgres internally
            self.pgvector_manager = PgVectorManager() if vector_store is None else vector_store
        else:
            # Используем ChromaDB (legacy)
            self.vector_store = vector_store or VectorStoreManager()
            self.pgvector_manager = None

        self._initialized = False

    async def initialize(self) -> Dict[str, bool]:
        """Initialize all storage backends."""

        logger.info(f"🔌 Initializing storage coordinator components (pgvector: {self.use_pgvector})...")

        results = {
            "postgres": False,
            "redis": False,
            "vector_store": False,
            "pgvector": False,
        }

        # Инициализация PostgreSQL (обязательно)
        results["postgres"] = await self.postgres.initialize()
        
        # Инициализация Redis
        results["redis"] = await self.redis.initialize()
        
        if self.use_pgvector:
            # Используем pgvector
            results["pgvector"] = await self.pgvector_manager.initialize()
        else:
            # Используем ChromaDB
            results["vector_store"] = await self.vector_store.initialize()

        success_count = sum(1 for ok in results.values() if ok)
        logger.info(f"📦 Storage init summary: {success_count}/4 components ready")
        logger.info(f"💾 Vector storage: {'pgvector' if self.use_pgvector else 'ChromaDB'}")

        self._initialized = all(results.values())
        return results

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def close_all(self) -> None:
        """Close all connections."""

        logger.info("🔒 Closing storage coordinator components...")
        await self.postgres.close()
        await self.redis.close()
        # Vector store does not expose explicit close method yet
        logger.info("✅ Storage coordinator components closed")

    async def store_document_complete(
        self,
        file_path: str,
        chunks: List[TextChunk],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store document in Postgres + Vector Store + Redis cache."""

        metadata = metadata or {}
        force_reprocess = metadata.get("force_reprocess", False)

        file_path_obj = Path(file_path).expanduser().resolve()
        file_hash: Optional[str] = None
        file_size: Optional[int] = None

        if file_path_obj.exists():
            try:
                content = file_path_obj.read_bytes()
                file_hash = hashlib.sha256(content).hexdigest()
                file_size = len(content)
            except Exception as exc:  # pragma: no cover - filesystem issues
                logger.warning("⚠️ Не удалось вычислить хеш файла %s: %s", file_path_obj, exc)

        original_filename = (
            metadata.get("original_filename")
            or metadata.get("filename")
            or metadata.get("file_name")
            or file_path_obj.name
        )

        document_data = {
            "file_path": str(file_path_obj),
            "file_name": original_filename,
            "file_size": file_size,
            "file_hash": file_hash,
            "document_type": metadata.get("document_type", "general"),
            "processed_at": datetime.now(),
            "status": metadata.get("status", "completed"),
            "metadata": metadata,
        }

        doc_id: Optional[str] = None
        try:
            if force_reprocess:
                doc_id, is_duplicate = await self.postgres.insert_document(
                    document_data, skip_duplicates=True
                )
            else:
                doc_id, is_duplicate = await self.postgres.insert_document(document_data)
        except Exception as exc:
            logger.error("❌ Ошибка сохранения документа в PostgreSQL: %s", exc)
            return {
                "success": False,
                "document_id": doc_id,
                "duplicate": False,
                "error": str(exc),
            }

        if is_duplicate:
            logger.info("⏭️ Пропускаем обработку дубликата: %s", original_filename)
            return {
                "success": True,
                "document_id": doc_id,
                "duplicate": True,
                "message": f"Документ '{original_filename}' уже существует в системе",
                "file_hash": file_hash,
            }

        chunks_stored = 0
        if chunks:
            try:
                await self.postgres.insert_chunks(chunks, doc_id)
                chunks_stored = len(chunks)
            except Exception as exc:
                logger.error("❌ Ошибка сохранения чанков в PostgreSQL: %s", exc)

            try:
                if self.use_pgvector:
                    added = await self.pgvector_manager.add_documents(chunks)
                    storage_name = "pgvector"
                else:
                    added = await self.vector_store.add_documents(chunks)
                    storage_name = "ChromaDB"
                    
                if not added:
                    logger.warning("⚠️ Vector store не подтвердил сохранение чанков для %s", doc_id)
            except Exception as exc:
                if self.use_pgvector:
                    logger.error("❌ Ошибка сохранения чанков в pgvector: %s", exc)
                else:
                    logger.error("❌ Ошибка сохранения чанков в ChromaDB: %s", exc)

        cache_payload = {
            "id": doc_id,
            "file_name": original_filename,
            "document_type": document_data["document_type"],
            "file_hash": file_hash,
            "metadata": metadata,
            "processed_at": document_data["processed_at"].isoformat(),
        }

        try:
            await self.redis.set_cache(f"document:{doc_id}", cache_payload, expire=86400)
        except Exception as exc:
            logger.warning("⚠️ Не удалось сохранить данные документа в Redis: %s", exc)

        return {
            "success": True,
            "document_id": doc_id,
            "duplicate": False,
            "chunks_stored": chunks_stored,
            "file_hash": file_hash,
            "storage_locations": ["postgres", "vector_store", "redis"],
        }

    async def search_documents(
        self,
        query: str,
        limit: Optional[int] = None,
        use_cache: bool = True,
        max_results: Optional[int] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Proxy search to vector store, optionally using Redis cache."""

        effective_limit = max_results if max_results is not None else limit or 10

        cache_key = None
        if use_cache:
            cache_key = f"search:{query}:{effective_limit}"
            cached = await self.redis.get_cache(cache_key)
            if cached:
                logger.debug("🎯 StorageCoordinator cache hit for %s", cache_key)
                return cached

        if self.use_pgvector:
            results = await self.pgvector_manager.search_similar(query, effective_limit)
        else:
            results = await self.vector_store.search_similar(query, effective_limit)

        if cache_key and results:
            await self.redis.set_cache(cache_key, results, expire=1800)

        return results

    async def get_health_status(self) -> Dict[str, Any]:
        """Report connectivity of all storage components."""

        status = {
            "postgres": {
                "connected": self.postgres.pool is not None,
                "pool_size": len(self.postgres.pool._holders) if self.postgres.pool else 0,
            },
            "redis": {
                "connected": self.redis.client is not None,
            },
        }
        
        if self.use_pgvector:
            status["pgvector"] = {
                "connected": self.pgvector_manager.postgres is not None,
                "database": "PostgreSQL + pgvector",
            }
        else:
            status["vector_store"] = {
                "connected": self.vector_store.collection is not None,
            }
        
        return status


async def create_storage_coordinator(use_pgvector: bool = False) -> StorageCoordinator:
    """Create a fully initialized coordinator instance."""
    
    coordinator = StorageCoordinator(use_pgvector=use_pgvector)
    await coordinator.initialize()
    return coordinator

