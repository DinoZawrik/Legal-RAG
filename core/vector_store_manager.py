#!/usr/bin/env python3
"""
Vector Store Manager
Модуль для работы с векторным хранилищем ChromaDB.

Включает функциональность:
- Подключение к ChromaDB
- Создание эмбеддингов через локальный Giga-Embeddings сервер (МИГРАЦИЯ v2.0)
- Хранение и поиск документов
- Поддержка различных типов чанков

МИГРАЦИЯ v2.0 (13.10.2025):
- Удалена зависимость от Google Gemini API
- Использует локальный HTTP сервер (localhost:8001)
- Более быстрая генерация embeddings (без network latency)
- Совместимость с ChromaDB (1024-dim vectors)
"""

import json
import logging
import uuid
import asyncio
import os
from typing import Dict, List, Optional, Any

# Core imports
from core.infrastructure_suite import SETTINGS, TextChunk

# External imports
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    # NEW: Local embeddings client (заменяет Google Genai)
    from core.giga_local_embeddings_client import GigaLocalEmbeddingsClient

    # LEGACY: Старые импорты (удалим после полной миграции)
    # from google import genai
    # from core.gemini_rate_limiter import GeminiRateLimiter
    # from core.api_key_manager import get_key_manager

except ImportError as e:
    logging.warning(f"Vector store dependencies not available: {e}")
    GigaLocalEmbeddingsClient = None

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base exception for database errors."""
    pass


class VectorStoreManager:
    """
    Менеджер для работы с векторным хранилищем.
    Объединяет функциональность из storage_indexing.py
    """

    def __init__(self):
        self.client = None # ChromaDB client
        self.collection = None
        self.embedding_model = None

    async def initialize(self) -> bool:
        """Инициализация векторного хранилища через Docker ChromaDB."""
        try:
            # Context7 best practice: Use AsyncHttpClient
            self.client = await chromadb.AsyncHttpClient(
                host=SETTINGS.CHROMA_HOST,
                port=SETTINGS.CHROMA_PORT,
                settings=ChromaSettings(anonymized_telemetry=False)
            )

            # HNSW parameters for Russian legal text (Context7 optimized)
            hnsw_metadata = {
                "description": "Document embeddings with HNSW optimization",
                "hnsw:space": "cosine", # Cosine similarity for embeddings
                "hnsw:construction_ef": 200, # Build accuracy (good for ~250 chunks)
                "hnsw:search_ef": 100, # Query accuracy (optimal for 5-10 results)
                "hnsw:M": 16 # Graph connectivity (standard)
            }

            # Создание или получение коллекции
            try:
                self.collection = await self.client.get_collection(SETTINGS.DEFAULT_COLLECTION_NAME)
                logger.info(f"Найдена существующая коллекция '{SETTINGS.DEFAULT_COLLECTION_NAME}' в ChromaDB")
            except Exception:
                self.collection = await self.client.create_collection(
                    name=SETTINGS.DEFAULT_COLLECTION_NAME,
                    metadata=hnsw_metadata
                )
                logger.info(f"Создана новая коллекция '{SETTINGS.DEFAULT_COLLECTION_NAME}' с HNSW параметрами")

            # МИГРАЦИЯ v2.0: Локальный embeddings сервер вместо Google Gemini API
            if GigaLocalEmbeddingsClient is None:
                raise ImportError("GigaLocalEmbeddingsClient не доступен. Проверьте core/giga_local_embeddings_client.py")

            # Инициализация HTTP client для локального embeddings сервера
            embeddings_url = os.getenv('EMBEDDINGS_SERVER_URL', 'http://localhost:8001')
            self.embeddings_client = GigaLocalEmbeddingsClient(base_url=embeddings_url)

            # Health check локального сервера
            try:
                health = await self.embeddings_client.health_check()
                logger.info(f" Embeddings сервер доступен: {health}")

                # Получаем информацию о модели
                info = await self.embeddings_client.get_model_info()
                self.embedding_model = info.get('model_name', 'giga-embeddings-instruct')
                self.embedding_dimension = info.get('embedding_dimension', 1024)

                logger.info(f" Модель: {self.embedding_model}, Размерность: {self.embedding_dimension}")

            except Exception as e:
                logger.error(f" Не удалось подключиться к embeddings серверу на {embeddings_url}: {e}")
                logger.error(" Убедитесь что сервер запущен: docker-compose -f docker-compose.embeddings.yml up -d")
                raise

            logger.info(f" Vector store инициализирован с локальным Giga-Embeddings сервером ({embeddings_url})")
            return True

        except Exception as e:
            logger.error(f" Ошибка инициализации vector store: {e}")
            return False

    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        МИГРАЦИЯ v2.0: Создание эмбеддингов через локальный Giga-Embeddings сервер.

        Улучшения по сравнению с Gemini API:
        - Более быстрая генерация (без network latency к external API)
        - Не требует API ключей и ротации
        - Батчинг обрабатывается на стороне сервера
        - Надёжнее (нет rate limits)
        """
        try:
            if not texts:
                logger.warning(" Пустой список текстов для генерации embeddings")
                return []

            logger.info(f" Создание embeddings для {len(texts)} текстов через локальный сервер")

            # Вызов локального embeddings сервера (один запрос для всех текстов!)
            embeddings = await self.embeddings_client.generate_embeddings(texts)

            # Валидация размерности
            if embeddings and len(embeddings) > 0:
                actual_dim = len(embeddings[0])
                expected_dim = getattr(self, 'embedding_dimension', 1024)

                logger.info(f" Получено {len(embeddings)} embedding(s), размерность: {actual_dim}")

                if actual_dim != expected_dim:
                    logger.warning(f" Размерность не совпадает: ожидали {expected_dim}, получили {actual_dim}")
                    # Обновляем ожидаемую размерность
                    self.embedding_dimension = actual_dim

            return embeddings

        except Exception as e:
            logger.error(f" Ошибка создания embeddings через локальный сервер: {e}")
            logger.error(f" Проверьте что embeddings сервер запущен: docker-compose -f docker-compose.embeddings.yml up -d")
            return []

    async def add_documents(self, chunks: List) -> bool:
        """Добавление документов в векторное хранилище. Поддерживает TextChunk, TableChunk, AnyChunk."""
        try:
            if not chunks:
                return True

            # Подготовка данных с поддержкой разных типов чанков
            texts = []
            ids = []
            metadatas = []

            batch_ids = set()

            for chunk in chunks:
                # Извлекаем текст в зависимости от типа чанка
                text_content = self._extract_text_from_chunk(chunk)
                if text_content: # Только если есть текстовое содержимое
                    texts.append(text_content)

                    # Безопасное получение ID чанка
                    chunk_id = None
                    if hasattr(chunk, 'id'):
                        chunk_id = chunk.id
                        # Если ID - это словарь, преобразуем в строку или извлекаем нужное поле
                        if isinstance(chunk_id, dict):
                            chunk_id = chunk_id.get('id') or str(chunk_id)
                        elif not isinstance(chunk_id, str):
                            chunk_id = str(chunk_id)

                    # Генерируем ID если его нет
                    if not chunk_id:
                        chunk_id = f"chunk_{uuid.uuid4().hex[:8]}"

                    # Обеспечиваем уникальность идентификаторов в пакетной загрузке
                    if chunk_id in batch_ids:
                        base_id = chunk_id
                        suffix = 1
                        while True:
                            candidate = f"{base_id}__{suffix}"
                            if candidate not in batch_ids:
                                chunk_id = candidate
                                logger.debug(
                                    " Обнаружен дубликат chunk_id %s, переименован в %s",
                                    base_id,
                                    chunk_id,
                                )
                                break
                            suffix += 1

                    batch_ids.add(chunk_id)

                    ids.append(chunk_id)

                    # Обрабатываем метаданные
                    chunk_metadata = getattr(chunk, 'metadata', {}).copy()
                    if hasattr(chunk, 'chunk_type'):
                        chunk_metadata['chunk_type'] = chunk.chunk_type

                    # Специальная обработка для контекстуальных чанков (ContextualChunk)
                    # Проверяем прямые атрибуты чанка (ContextualChunk)
                    if hasattr(chunk, 'slide_number') and hasattr(chunk, 'elements'):
                        # Добавляем контекстуальные поля в метаданные
                        chunk_metadata.update({
                            'slide_number': getattr(chunk, 'slide_number', None),
                            'slide_title': getattr(chunk, 'slide_title', None),
                            'slide_type': getattr(chunk, 'slide_type', None),
                            'elements': getattr(chunk, 'elements', []),
                            'relationships': getattr(chunk, 'relationships', []),
                            'key_insights': getattr(chunk, 'key_insights', []),
                            'context_summary': getattr(chunk, 'context_summary', None),
                            'contextual_extraction': True # Флаг что это контекстуальный чанк
                        })
                        logger.info(f" Добавлены контекстуальные метаданные: {len(chunk.elements)} элементов, {len(chunk.relationships)} связей")
                    # Альтернативная проверка для чанков где контекстуальные данные в content
                    elif hasattr(chunk, 'content') and hasattr(chunk.content, 'slide_number'):
                        contextual_content = chunk.content
                        # Добавляем контекстуальные поля в метаданные
                        chunk_metadata.update({
                            'slide_number': getattr(contextual_content, 'slide_number', None),
                            'slide_title': getattr(contextual_content, 'slide_title', None),
                            'slide_type': getattr(contextual_content, 'slide_type', None),
                            'elements': getattr(contextual_content, 'elements', []),
                            'relationships': getattr(contextual_content, 'relationships', []),
                            'key_insights': getattr(contextual_content, 'key_insights', []),
                            'context_summary': getattr(contextual_content, 'context_summary', None),
                            'contextual_extraction': True # Флаг что это контекстуальный чанк
                        })
                        logger.info(f" Добавлены контекстуальные метаданные из content: {len(contextual_content.elements)} элементов, {len(contextual_content.relationships)} связей")

                    metadatas.append(chunk_metadata)

            if not texts:
                logger.warning(" Нет текстового содержимого для сохранения в vector store")
                return True

            # Создание эмбеддингов
            embeddings = await self.create_embeddings(texts)

            if not embeddings:
                raise DatabaseError("Failed to create embeddings")

            # Проверка размеров массивов перед добавлением
            if len(embeddings) != len(texts):
                logger.error(f" Несоответствие размеров: embeddings={len(embeddings)}, texts={len(texts)}")
                # Обрезаем эмбеддинги до нужного размера
                embeddings = embeddings[:len(texts)]
                logger.warning(f" Обрезали embeddings до {len(embeddings)} элементов")

            if len(metadatas) != len(texts):
                logger.error(f" Несоответствие размеров: metadatas={len(metadatas)}, texts={len(texts)}")
                metadatas = metadatas[:len(texts)]

            if len(ids) != len(texts):
                logger.error(f" Несоответствие размеров: ids={len(ids)}, texts={len(texts)}")
                ids = ids[:len(texts)]

            logger.info(f" Проверка размеров: texts={len(texts)}, embeddings={len(embeddings)}, metadatas={len(metadatas)}, ids={len(ids)}")

            # Context7 best practice: await async operations
            await self.collection.add(
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )

            logger.info(f"Добавлено {len(texts)} документов в vector store (из {len(chunks)} чанков)")
            return True

        except Exception as e:
            logger.error(f" Ошибка добавления документов в vector store: {e}")
            return False

    def _extract_text_from_chunk(self, chunk) -> str:
        """Извлекает текстовое содержимое из различных типов чанков."""
        try:
            # TextChunk - стандартный текстовый чанк
            if hasattr(chunk, 'text') and isinstance(chunk.text, str):
                logger.debug(f" Извлекаем text из TextChunk: {len(chunk.text)} символов")
                return chunk.text

            # AnyChunk - универсальный чанк (проверяем первым, так как содержит разные типы)
            elif hasattr(chunk, 'content') and hasattr(chunk, 'chunk_type'):
                chunk_type = getattr(chunk, 'chunk_type', '')
                content = chunk.content

                logger.debug(f" Обрабатываем AnyChunk с типом: '{chunk_type}', content type: {type(content).__name__}")

                # Контекстуальный чанк из Universal Contextual Extraction v2.0
                if chunk_type == 'contextual' and hasattr(content, 'searchable_text'):
                    text_length = len(content.searchable_text) if content.searchable_text else 0
                    logger.debug(f" Извлекаем searchable_text из ContextualChunk: {text_length} символов")
                    return content.searchable_text or ""

                # TableChunk - табличные данные
                elif chunk_type == 'table':
                    if hasattr(content, 'table_content') and isinstance(content.table_content, str):
                        logger.debug(f" Извлекаем table_content из TableChunk: {len(content.table_content)} символов")
                        return content.table_content
                    elif hasattr(content, 'content') and isinstance(content.content, str):
                        logger.debug(f" Извлекаем content из TableChunk: {len(content.content)} символов")
                        return content.content
                    elif hasattr(content, 'text') and isinstance(content.text, str):
                        logger.debug(f" Извлекаем text из TableChunk: {len(content.text)} символов")
                        return content.text

                # Чанк с графиком или диаграммой
                elif chunk_type == 'chart' and isinstance(content, str):
                    logger.debug(f" Извлекаем content из chart chunk: {len(content)} символов")
                    return content

                # Чанк со связями
                elif chunk_type == 'relationship' and isinstance(content, str):
                    logger.debug(f" Извлекаем content из relationship chunk: {len(content)} символов")
                    return content

                # Общий случай для AnyChunk - пробуем различные атрибуты content
                if hasattr(content, 'text') and isinstance(content.text, str):
                    logger.debug(f" Извлекаем text из content: {len(content.text)} символов")
                    return content.text
                elif hasattr(content, 'content') and isinstance(content.content, str):
                    logger.debug(f" Извлекаем content.content: {len(content.content)} символов")
                    return content.content
                elif isinstance(content, str):
                    logger.debug(f" Content сам является строкой: {len(content)} символов")
                    return content
                elif hasattr(content, '__str__'):
                    str_content = str(content)
                    logger.debug(f" Преобразовали content в строку: {len(str_content)} символов")
                    return str_content

            # TableChunk - отдельная проверка для совместимости
            elif hasattr(chunk, 'table_content') and isinstance(chunk.table_content, str):
                logger.debug(f" Извлекаем table_content напрямую: {len(chunk.table_content)} символов")
                return chunk.table_content

            # Если chunk сам является строкой (edge case)
            elif isinstance(chunk, str):
                logger.debug(f" Chunk сам является строкой: {len(chunk)} символов")
                return chunk

            # Резервный вариант - ищем текстовые атрибуты
            for attr in ['text', 'content', 'data', 'searchable_text']:
                if hasattr(chunk, attr):
                    value = getattr(chunk, attr)
                    if isinstance(value, str) and value.strip():
                        logger.debug(f" Найден текст в атрибуте '{attr}': {len(value)} символов")
                        return value

            # Последний fallback - преобразование к строке
            if hasattr(chunk, '__str__'):
                str_chunk = str(chunk)
                if len(str_chunk.strip()) > 0 and not str_chunk.startswith('<'): # Избегаем объектных представлений
                    logger.debug(f" Преобразовали chunk в строку: {len(str_chunk)} символов")
                    return str_chunk

            logger.warning(f" Не удалось извлечь текст из чанка типа {type(chunk).__name__}, атрибуты: {dir(chunk)}")
            return ""

        except Exception as e:
            logger.error(f" Ошибка извлечения текста из чанка: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return ""

    async def search_similar(self, query: str, limit: int = 10) -> List[Dict]:
        """Поиск похожих документов."""
        try:
            # Создание эмбеддинга для запроса
            embeddings = await self.create_embeddings([query])
            if not embeddings:
                raise DatabaseError("Failed to create query embedding")
            query_embedding = embeddings[0]

            # Context7 best practice: await async operations
            results = await self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                include=['documents', 'metadatas', 'distances']
            )

            # Форматирование результатов
            formatted_results = []
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'id': results['ids'][0][i],
                    'text': results['documents'][0][i],
                    'document': results['documents'][0][i], # Дублируем для совместимости
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i],
                    'similarity': 1 - results['distances'][0][i] # Конвертация в similarity
                })

            logger.info(f" Найдено {len(formatted_results)} похожих документов")
            return formatted_results

        except Exception as e:
            logger.error(f" Ошибка поиска похожих документов: {e}")
            return []

    async def get_collection_stats(self) -> Dict:
        """Получение статистики коллекции."""
        try:
            # Context7 best practice: await async operations
            count = await self.collection.count()
            return {
                "total_documents": count,
                "collection_name": self.collection.name,
                "metadata": self.collection.metadata
            }

        except Exception as e:
            logger.error(f" Ошибка получения статистики: {e}")
            return {}


# Factory functions for easy instantiation
async def create_vector_store() -> VectorStoreManager:
    """Создание менеджера vector store."""
    manager = VectorStoreManager()
    await manager.initialize()
    return manager


# Compatibility wrapper functions
async def add_documents_to_vector_store(vector_store, chunks):
    """Обертка для совместимости с устаревшим storage_indexing.py"""
    if hasattr(vector_store, 'add_documents'):
        return await vector_store.add_documents(chunks)
    else:
        logger.error(" Vector store не поддерживает add_documents")
        return False

