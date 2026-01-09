#!/usr/bin/env python3
"""
🔌 Giga-Embeddings Local Client
HTTP client для взаимодействия с локальным embeddings сервером.

Заменяет прямые вызовы Google Genai API на HTTP запросы к localhost:8001
Совместим с VectorStoreManager без изменения интерфейса.

Usage:
    from core.giga_local_embeddings_client import GigaLocalEmbeddingsClient

    client = GigaLocalEmbeddingsClient()
    embeddings = await client.generate_embeddings(["текст 1", "текст 2"])
"""

import logging
import os
from typing import List, Optional
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class GigaLocalEmbeddingsClient:
    """
    Async HTTP client для локального Giga-Embeddings сервера.

    Attributes:
        base_url: URL embeddings сервера (по умолчанию http://localhost:8001)
        timeout: Таймаут для HTTP запросов (секунды)
        max_retries: Максимальное число попыток при ошибках
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        Инициализация клиента.

        Args:
            base_url: URL embeddings сервера (из env EMBEDDINGS_SERVER_URL или http://localhost:8001)
            timeout: Таймаут для запросов в секундах
            max_retries: Число повторных попыток при ошибках
        """
        self.base_url = base_url or os.getenv("EMBEDDINGS_SERVER_URL", "http://localhost:8001")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries

        # Remove trailing slash
        self.base_url = self.base_url.rstrip("/")

        logger.info(f"🔌 Initialized GigaLocalEmbeddingsClient with base_url={self.base_url}")

    async def health_check(self) -> dict:
        """
        Проверка здоровья embeddings сервера.

        Returns:
            dict: Статус сервера {"status": "healthy", "model_loaded": True, ...}

        Raises:
            aiohttp.ClientError: Если сервер недоступен
        """
        url = f"{self.base_url}/health"

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise aiohttp.ClientError(f"Health check failed: {response.status}")

                data = await response.json()
                logger.info(f"✅ Health check OK: {data}")
                return data

    async def get_model_info(self) -> dict:
        """
        Получение информации о модели.

        Returns:
            dict: Информация о модели {"model_name": "...", "embedding_dimension": 1024, ...}
        """
        url = f"{self.base_url}/info"

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise aiohttp.ClientError(f"Model info failed: {response.status}")

                data = await response.json()
                logger.info(f"📊 Model info: {data}")
                return data

    async def generate_embeddings(
        self,
        texts: List[str],
        model: str = "giga-embeddings-instruct"
    ) -> List[List[float]]:
        """
        Генерация embeddings для списка текстов.

        Args:
            texts: Список текстов для векторизации
            model: Название модели (игнорируется сервером, но сохраняется для совместимости)

        Returns:
            List[List[float]]: Список векторов embeddings (каждый вектор - список float)

        Raises:
            aiohttp.ClientError: При ошибках HTTP запроса
            ValueError: При некорректном ответе от сервера
        """
        if not texts:
            logger.warning("⚠️ Empty texts list provided")
            return []

        url = f"{self.base_url}/v1/embeddings"

        payload = {
            "input": texts,
            "model": model
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(url, json=payload) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"❌ Embeddings API error (attempt {attempt}/{self.max_retries}): {response.status} - {error_text}")

                            if attempt < self.max_retries:
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                                continue
                            else:
                                raise aiohttp.ClientError(f"Embeddings generation failed after {self.max_retries} attempts: {response.status}")

                        data = await response.json()

                        # Валидация ответа
                        if "data" not in data:
                            raise ValueError(f"Invalid response format: missing 'data' field")

                        # Извлечение embeddings из response
                        embeddings = [item["embedding"] for item in data["data"]]

                        logger.info(f"✅ Generated {len(embeddings)} embedding(s) for {len(texts)} text(s)")

                        return embeddings

            except aiohttp.ClientError as e:
                logger.error(f"❌ HTTP error (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

            except Exception as e:
                logger.error(f"❌ Unexpected error (attempt {attempt}/{self.max_retries}): {e}", exc_info=True)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

        # Should not reach here
        raise RuntimeError("Failed to generate embeddings after all retries")

    async def generate_embedding(self, text: str, model: str = "giga-embeddings-instruct") -> List[float]:
        """
        Генерация embedding для одного текста (helper method).

        Args:
            text: Текст для векторизации
            model: Название модели

        Returns:
            List[float]: Вектор embedding
        """
        embeddings = await self.generate_embeddings([text], model=model)
        return embeddings[0] if embeddings else []


# Singleton instance (опционально)
_client_instance: Optional[GigaLocalEmbeddingsClient] = None


def get_embeddings_client() -> GigaLocalEmbeddingsClient:
    """
    Получить singleton instance клиента.

    Returns:
        GigaLocalEmbeddingsClient: Глобальный экземпляр клиента
    """
    global _client_instance

    if _client_instance is None:
        _client_instance = GigaLocalEmbeddingsClient()

    return _client_instance


# Пример использования
if __name__ == "__main__":
    async def main():
        client = GigaLocalEmbeddingsClient()

        # Health check
        try:
            health = await client.health_check()
            print(f"✅ Server health: {health}")
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return

        # Model info
        try:
            info = await client.get_model_info()
            print(f"📊 Model: {info['model_name']}, Dimension: {info['embedding_dimension']}")
        except Exception as e:
            print(f"❌ Model info failed: {e}")

        # Generate embeddings
        texts = [
            "Что такое концессионное соглашение?",
            "Плата концедента в ГЧП"
        ]

        try:
            embeddings = await client.generate_embeddings(texts)
            print(f"✅ Generated {len(embeddings)} embeddings")
            print(f"   Dimension: {len(embeddings[0])}")
            print(f"   First 5 values: {embeddings[0][:5]}")
        except Exception as e:
            print(f"❌ Embeddings generation failed: {e}")

    asyncio.run(main())
