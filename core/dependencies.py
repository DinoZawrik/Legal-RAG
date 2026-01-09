"""Dependency management for FastAPI services (Storage, Postgres, Redis, Vector Store)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, Optional

from fastapi import Depends

from core.storage_coordinator import StorageCoordinator, create_storage_coordinator
from core.postgres_manager import PostgresManager
from core.redis_manager import RedisManager
from core.vector_store_manager import VectorStoreManager


class DependencyContainer:
    """Holds lazily initialized shared resources with async-safe access."""

    def __init__(self) -> None:
        self._storage: Optional[StorageCoordinator] = None
        self._storage_lock = asyncio.Lock()

    async def get_storage(self) -> StorageCoordinator:
        if self._storage is None:
            async with self._storage_lock:
                if self._storage is None:
                    self._storage = await create_storage_coordinator()
        return self._storage

    async def get_postgres(self) -> PostgresManager:
        storage = await self.get_storage()
        return storage.postgres

    async def get_redis(self) -> RedisManager:
        storage = await self.get_storage()
        return storage.redis

    async def get_vector_store(self) -> VectorStoreManager:
        storage = await self.get_storage()
        return storage.vector_store

    async def shutdown(self) -> None:
        if self._storage is not None:
            await self._storage.close_all()
            self._storage = None


container = DependencyContainer()


async def get_storage() -> StorageCoordinator:
    """FastAPI dependency returning initialized StorageCoordinator."""

    return await container.get_storage()


async def get_postgres(storage: StorageCoordinator = Depends(get_storage)) -> PostgresManager:
    return storage.postgres


async def get_redis(storage: StorageCoordinator = Depends(get_storage)) -> RedisManager:
    return storage.redis


async def get_vector_store(storage: StorageCoordinator = Depends(get_storage)) -> VectorStoreManager:
    return storage.vector_store


StorageDep = Depends(get_storage)
PostgresDep = Depends(get_postgres)
RedisDep = Depends(get_redis)
VectorStoreDep = Depends(get_vector_store)


@asynccontextmanager
async def lifespan() -> AsyncIterator[DependencyContainer]:
    """FastAPI lifespan helper to start/shutdown shared dependencies."""

    await container.get_storage()
    try:
        yield container
    finally:
        await container.shutdown()


__all__ = [
    "DependencyContainer",
    "container",
    "StorageCoordinator",
    "PostgresManager",
    "RedisManager",
    "VectorStoreManager",
    "get_storage",
    "get_postgres",
    "get_redis",
    "get_vector_store",
    "StorageDep",
    "PostgresDep",
    "RedisDep",
    "VectorStoreDep",
    "lifespan",
]

