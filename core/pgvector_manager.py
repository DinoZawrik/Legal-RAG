"""PgVector Manager — PostgreSQL pgvector extension for vector similarity search.

Lightweight wrapper around PostgreSQL with pgvector extension.
Used as alternative to ChromaDB for all-in-one PostgreSQL deployment.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import asyncpg
except ImportError:
    asyncpg = None  # type: ignore[assignment]


class PgVectorManager:
    """Manage vector embeddings in PostgreSQL via pgvector extension."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or self._build_dsn()
        self.pool: Optional[Any] = None
        self.postgres: Optional[Any] = None
        self._initialized = False

    @staticmethod
    def _build_dsn() -> str:
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "legal_rag_db")
        user = os.getenv("POSTGRES_USER", "legal_rag_user")
        password = os.getenv("POSTGRES_PASSWORD", "")
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    async def initialize(self) -> bool:
        """Initialize pgvector tables in PostgreSQL."""
        if asyncpg is None:
            logger.warning("asyncpg not installed — pgvector manager unavailable")
            return False

        try:
            self.pool = await asyncpg.create_pool(self.dsn, min_size=2, max_size=5)
            self.postgres = self.pool

            async with self.pool.acquire() as conn:
                # Enable pgvector extension
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                # Create embeddings table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS document_embeddings (
                        id SERIAL PRIMARY KEY,
                        chunk_id TEXT UNIQUE,
                        content TEXT NOT NULL,
                        embedding vector(768),
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_vector
                    ON document_embeddings
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """)

            self._initialized = True
            logger.info("PgVector manager initialized")
            return True

        except Exception as e:
            logger.warning("PgVector initialization failed (non-critical): %s", e)
            self._initialized = False
            return False

    async def add_documents(self, chunks: List[Any]) -> bool:
        """Store document chunks with embeddings in pgvector."""
        if not self._initialized or not self.pool:
            logger.warning("PgVector not initialized, skipping add_documents")
            return False

        try:
            async with self.pool.acquire() as conn:
                for chunk in chunks:
                    chunk_id = getattr(chunk, "chunk_id", None) or getattr(chunk, "id", "")
                    text = getattr(chunk, "text", "") or getattr(chunk, "content", "")
                    embedding = getattr(chunk, "embedding", None)
                    metadata = getattr(chunk, "metadata", {})

                    if not text:
                        continue

                    if embedding:
                        await conn.execute(
                            """
                            INSERT INTO document_embeddings (chunk_id, content, embedding, metadata)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (chunk_id) DO UPDATE SET content = $2, embedding = $3, metadata = $4
                            """,
                            str(chunk_id), text, str(embedding), metadata if isinstance(metadata, dict) else {},
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO document_embeddings (chunk_id, content, metadata)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (chunk_id) DO UPDATE SET content = $2, metadata = $3
                            """,
                            str(chunk_id), text, metadata if isinstance(metadata, dict) else {},
                        )

            return True
        except Exception as e:
            logger.error("PgVector add_documents error: %s", e)
            return False

    async def search_similar(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for similar documents using pgvector cosine distance."""
        if not self._initialized or not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                # Fallback to text search if no embeddings available
                rows = await conn.fetch(
                    """
                    SELECT chunk_id, content, metadata,
                        ts_rank(to_tsvector('russian', content), plainto_tsquery('russian', $1)) as rank
                    FROM document_embeddings
                    WHERE to_tsvector('russian', content) @@ plainto_tsquery('russian', $1)
                    ORDER BY rank DESC
                    LIMIT $2
                    """,
                    query, limit,
                )

            return [
                {
                    "id": row["chunk_id"],
                    "text": row["content"],
                    "metadata": dict(row["metadata"]) if row["metadata"] else {},
                    "similarity": float(row["rank"]),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error("PgVector search error: %s", e)
            return []

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
            self.postgres = None
