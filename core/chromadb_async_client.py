#!/usr/bin/env python3
"""
ChromaDB Async Client Helper
Context7-validated async client for ChromaDB with HNSW optimization

Based on Context7 docs: /chroma-core/chroma
"""
import chromadb
from typing import Optional, Dict, Any
import logging


logger = logging.getLogger(__name__)


class ChromaDBAsyncClient:
    """
    Async wrapper for ChromaDB with HNSW parameter optimization

    Context7 Best Practices:
    - Use AsyncHttpClient for non-blocking operations
    - Configure HNSW parameters for accuracy/performance tradeoff
    - Proper async context management
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        ssl: bool = False,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize async ChromaDB client

        Args:
            host: ChromaDB server host
            port: ChromaDB server port
            ssl: Use SSL connection
            headers: Optional HTTP headers
        """
        self.host = host
        self.port = port
        self.ssl = ssl
        self.headers = headers
        self.client = None

    async def connect(self):
        """
        Connect to ChromaDB server asynchronously

        Context7 Pattern:
        ```python
        async def main():
            client = await chromadb.AsyncHttpClient(host='localhost', port=8000)
        ```
        """
        logger.info(f"Connecting to ChromaDB at {self.host}:{self.port}...")

        self.client = await chromadb.AsyncHttpClient(
            host=self.host,
            port=self.port,
            ssl=self.ssl,
            headers=self.headers
        )

        logger.info("[OK] ChromaDB async client connected")
        return self.client

    async def get_or_create_collection(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding_function=None,
        hnsw_space: str = "cosine",
        hnsw_construction_ef: int = 200,
        hnsw_search_ef: int = 100,
        hnsw_m: int = 16
    ):
        """
        Get or create collection with HNSW optimization

        HNSW Parameters (Context7 best practices):
        - hnsw_space: Distance metric ("cosine", "l2", "ip")
        - hnsw_construction_ef: Build accuracy (100-400, default 200)
          Higher = better accuracy, slower build time
        - hnsw_search_ef: Query accuracy (50-200, default 100)
          Higher = better recall, slower queries
        - hnsw_m: Graph connectivity (8-64, default 16)
          Higher = better accuracy, more memory

        For Russian legal text (our use case):
        - construction_ef=200: Good balance for 247 chunks
        - search_ef=100: Optimal for 5-10 result queries
        - m=16: Standard for medium-sized collections

        Args:
            name: Collection name
            metadata: Collection metadata
            embedding_function: Custom embedding function
            hnsw_space: HNSW distance metric
            hnsw_construction_ef: HNSW construction accuracy
            hnsw_search_ef: HNSW search accuracy
            hnsw_m: HNSW graph connectivity
        """
        if not self.client:
            await self.connect()

        # Build HNSW metadata
        hnsw_metadata = {
            "hnsw:space": hnsw_space,
            "hnsw:construction_ef": hnsw_construction_ef,
            "hnsw:search_ef": hnsw_search_ef,
            "hnsw:M": hnsw_m
        }

        # Merge with user metadata
        if metadata:
            hnsw_metadata.update(metadata)

        logger.info(f"Getting/creating collection '{name}' with HNSW params: "
                   f"space={hnsw_space}, construction_ef={hnsw_construction_ef}, "
                   f"search_ef={hnsw_search_ef}, M={hnsw_m}")

        collection = await self.client.get_or_create_collection(
            name=name,
            metadata=hnsw_metadata,
            embedding_function=embedding_function
        )

        logger.info(f"[OK] Collection '{name}' ready (async mode)")
        return collection

    async def heartbeat(self) -> int:
        """
        Check client connectivity

        Returns:
            Nanosecond timestamp from server
        """
        if not self.client:
            await self.connect()

        timestamp = await self.client.heartbeat()
        logger.debug(f"ChromaDB heartbeat: {timestamp}")
        return timestamp

    async def reset(self):
        """
        DESTRUCTIVE: Reset entire database

        WARNING: This clears ALL data!
        """
        if not self.client:
            await self.connect()

        logger.warning("[DESTRUCTIVE] Resetting ChromaDB database...")
        await self.client.reset()
        logger.warning("[DONE] Database reset")

    async def list_collections(self):
        """List all collections"""
        if not self.client:
            await self.connect()

        collections = await self.client.list_collections()
        logger.info(f"Collections: {[c.name for c in collections]}")
        return collections

    async def delete_collection(self, name: str):
        """Delete collection by name"""
        if not self.client:
            await self.connect()

        logger.info(f"Deleting collection '{name}'...")
        await self.client.delete_collection(name=name)
        logger.info(f"[OK] Collection '{name}' deleted")


# Singleton instance
_async_client: Optional[ChromaDBAsyncClient] = None


async def get_chromadb_async_client(
    host: str = "localhost",
    port: int = 8000,
    ssl: bool = False
) -> ChromaDBAsyncClient:
    """
    Get singleton ChromaDB async client

    Usage:
    ```python
    client = await get_chromadb_async_client()
    collection = await client.get_or_create_collection("documents")
    ```
    """
    global _async_client

    if _async_client is None:
        _async_client = ChromaDBAsyncClient(host=host, port=port, ssl=ssl)
        await _async_client.connect()

    return _async_client


# Migration helper for backward compatibility
def create_sync_wrapper(async_collection):
    """
    DEPRECATED: Temporary sync wrapper for migration period

    DO NOT USE in new code! Use async operations instead.
    """
    import asyncio

    class SyncCollectionWrapper:
        def __init__(self, async_coll):
            self._async_coll = async_coll
            self._loop = asyncio.get_event_loop()

        def get(self, **kwargs):
            return self._loop.run_until_complete(self._async_coll.get(**kwargs))

        def query(self, **kwargs):
            return self._loop.run_until_complete(self._async_coll.query(**kwargs))

        def add(self, **kwargs):
            return self._loop.run_until_complete(self._async_coll.add(**kwargs))

        def count(self):
            return self._loop.run_until_complete(self._async_coll.count())

    logger.warning("[DEPRECATED] Using sync wrapper for async collection. "
                  "Please migrate to async code!")
    return SyncCollectionWrapper(async_collection)
