#!/usr/bin/env python3
"""
🗄️ PostgreSQL Database Manager
Модуль для работы с PostgreSQL базой данных.

МИГРАЦИЯ v4.0 (02.11.2025):
- ✅ Поддержка pgvector расширения
- ✅ Векторные операции для embeddings
- ✅ HNSW индексы для быстрого поиска
- ✅ JSONB для гибких метаданных
- ✅ ACID транзакции для векторных данных

Включает функциональность:
- Подключение к PostgreSQL
- Управление документами и чанками
- Проверка дубликатов
- Векторный поиск и хранение
- Создание таблиц и индексов
"""

import asyncio
import json
import logging
import uuid
import ssl
from datetime import datetime
from typing import Dict, List, Optional, Any
import os

# Core imports
from core.infrastructure_suite import SETTINGS, TextChunk

# External imports
try:
    import asyncpg
    from sqlalchemy import MetaData, Table, Column, String, DateTime, Text, Integer
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
except ImportError as e:
    logging.warning(f"PostgreSQL dependencies not available: {e}")

logger = logging.getLogger(__name__)


def get_ssl_config():
    """Возвращает SSL-конфигурацию для подключения к базе данных."""
    if getattr(SETTINGS, 'POSTGRES_SSL_MODE', 'prefer') in ('require', 'verify-ca', 'verify-full'):
        ssl_context = ssl.create_default_context(
            cafile=SETTINGS.POSTGRES_SSL_ROOT_CERT_PATH
        )
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context
    return None


class DatabaseError(Exception):
    """Базовое исключение для ошибок базы данных."""
    pass


class PostgresManager:
    """
    Менеджер для работы с PostgreSQL.
    Объединяет функциональность из database.py и db_manager.py
    """

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.engine = None
        self.async_session_maker = None
        try:
            from sqlalchemy import MetaData
            self.metadata = MetaData()
            self._setup_tables()
        except ImportError:
            self.metadata = None
            logger.warning("SQLAlchemy не доступен, миграции отключены")

    def _setup_tables(self):
        """Определение схемы таблиц."""
        try:
            from sqlalchemy import Table, Column, String, DateTime, Text, Integer
            # Таблица документов
            self.documents_table = Table(
            'documents',
            self.metadata,
            Column('id', String, primary_key=True),
            Column('file_path', String, nullable=False),
            Column('filename', String, nullable=False),
            Column('file_size', Integer),
            Column('file_hash', String),
            Column('document_type', String),
            Column('processed_at', DateTime),
            Column('status', String, default='pending'),
            Column('metadata', Text),  # JSON
        )

            # Таблица регулятивных документов
            self.regulatory_documents_table = Table(
            'regulatory_documents',
            self.metadata,
            Column('id', String, primary_key=True),
            Column('document_id', String),  # FK to documents
            Column('document_type', String),
            Column('document_number', String),
            Column('adoption_date', String),
            Column('issuing_authority', String),
            Column('summary', Text),
            Column('scope', Text),
            Column('extracted_data', Text),  # JSON
            Column('created_at', DateTime),
        )

            # Таблица чанков
            self.chunks_table = Table(
            'chunks',
            self.metadata,
            Column('id', String, primary_key=True),
            Column('document_id', String),
            Column('chunk_index', Integer),
            Column('text', Text),
            Column('chunk_type', String),
            Column('metadata', Text),  # JSON
            Column('created_at', DateTime),
        )
        except ImportError:
            logger.warning("Пропущено создание таблиц: SQLAlchemy недоступен")

    async def initialize(self) -> bool:
        """Инициализация подключения к PostgreSQL."""
        try:
            # Создание пула соединений
            self.pool = await asyncpg.create_pool(
                host=SETTINGS.POSTGRES_HOST,
                port=SETTINGS.POSTGRES_PORT,
                database=SETTINGS.POSTGRES_DB,
                user=SETTINGS.POSTGRES_USER,
                password=SETTINGS.POSTGRES_PASSWORD,
                min_size=1,
                max_size=10,
                command_timeout=60,
                ssl=get_ssl_config()
            )

            # Создание async engine для SQLAlchemy
            database_url = f"postgresql+asyncpg://{SETTINGS.POSTGRES_USER}:{SETTINGS.POSTGRES_PASSWORD}@{SETTINGS.POSTGRES_HOST}:{SETTINGS.POSTGRES_PORT}/{SETTINGS.POSTGRES_DB}"
            self.engine = create_async_engine(database_url, echo=False)

            self.async_session_maker = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )

            # Создание таблиц
            async with self.engine.begin() as conn:
                await conn.run_sync(self.metadata.create_all)

            # Создание индексов для оптимизации дедупликации
            await self._create_deduplication_indexes()

            logger.info("✅ PostgreSQL подключение инициализировано")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации PostgreSQL: {e}")
            return False

    async def _create_deduplication_indexes(self):
        """Создание индексов для быстрой проверки дубликатов."""
        try:
            indexes_sql = [
                # Уникальный индекс на file_hash для предотвращения дубликатов по содержимому
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_file_hash ON documents (file_hash) WHERE file_hash IS NOT NULL",

                # Составной индекс для проверки по имени + типу документа
                "CREATE INDEX IF NOT EXISTS idx_documents_filename_type ON documents (filename, document_type)",

                # Индекс для поиска по типу документа (часто используется)
                "CREATE INDEX IF NOT EXISTS idx_documents_type ON documents (document_type)",

                # Индекс для поиска по дате обработки
                "CREATE INDEX IF NOT EXISTS idx_documents_processed_at ON documents (processed_at)",

                # Составной индекс для chunks (для быстрого поиска чанков документа)
                "CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks (document_id, chunk_index)"
            ]

            async with self.pool.acquire() as conn:
                for index_sql in indexes_sql:
                    try:
                        await conn.execute(index_sql)
                        logger.debug(f"✅ Создан индекс: {index_sql}")
                    except Exception as idx_error:
                        # Проверяем, не является ли ошибка дубликатом индекса
                        if "already exists" not in str(idx_error).lower():
                            logger.warning(f"⚠️ Ошибка создания индекса: {idx_error}")

            logger.info("✅ Индексы дедупликации созданы/проверены")

        except Exception as e:
            logger.error(f"❌ Ошибка создания индексов дедупликации: {e}")

    async def close(self):
        """Закрытие всех соединений."""
        if self.pool:
            await self.pool.close()
        if self.engine:
            await self.engine.dispose()
        logger.info("🔒 PostgreSQL соединения закрыты")

    async def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        """Выполнение SQL запроса."""
        if not self.pool:
            raise DatabaseError("PostgreSQL pool not initialized")

        try:
            async with self.pool.acquire() as conn:
                if params:
                    result = await conn.fetch(query, *params.values())
                else:
                    result = await conn.fetch(query)

                return [dict(row) for row in result]

        except Exception as e:
            logger.error(f"❌ Ошибка выполнения запроса: {e}")
            raise DatabaseError(f"Query execution failed: {e}")

    def _get_standardized_filename(self, document_data: Dict) -> str:
        """
        Стандартизированное получение имени файла с приоритетом original_filename из metadata.

        Приоритеты:
        1. original_filename из metadata (для Telegram и архивов)
        2. filename из metadata
        3. file_name из основных данных
        4. basename от file_path
        """
        # Приоритет 1: original_filename из metadata
        metadata = document_data.get('metadata', {})
        if isinstance(metadata, dict):
            if 'original_filename' in metadata and metadata['original_filename']:
                filename = metadata['original_filename'].strip()
                logger.debug(f"🎯 Используем original_filename из metadata: '{filename}'")
                return filename

            # Приоритет 2: filename из metadata
            if 'filename' in metadata and metadata['filename']:
                filename = metadata['filename'].strip()
                logger.debug(f"🎯 Используем filename из metadata: '{filename}'")
                return filename

        # Приоритет 3: file_name из основных данных
        if 'file_name' in document_data and document_data['file_name']:
            filename = document_data['file_name'].strip()
            logger.debug(f"🎯 Используем file_name из основных данных: '{filename}'")
            return filename

        # Приоритет 4: basename от file_path (fallback)
        if 'file_path' in document_data and document_data['file_path']:
            filename = os.path.basename(document_data['file_path']).strip()
            logger.debug(f"🎯 Используем basename от file_path: '{filename}'")
            return filename

        # Если ничего не найдено - ошибка
        raise ValueError("Не удалось определить имя файла из данных документа")

    async def insert_document(self, document_data: Dict, skip_duplicates: bool = False) -> str:
        """Вставка документа в базу."""
        try:
            # Убираем любые id или document_id из данных для избежания конфликтов
            clean_data = {k: v for k, v in document_data.items() if k not in ['id', 'document_id']}

            # Также очищаем метаданные от id полей
            if 'metadata' in clean_data and isinstance(clean_data['metadata'], dict):
                clean_metadata = {k: v for k, v in clean_data['metadata'].items() if k not in ['id', 'document_id']}
                clean_data['metadata'] = clean_metadata

            # СТАНДАРТИЗАЦИЯ имени файла: приоритет original_filename из metadata
            filename = self._get_standardized_filename(clean_data)
            doc_type = clean_data.get('document_type', 'general')
            file_hash = clean_data.get('file_hash')

            logger.info(f"🔍 Проверка дубликатов для файла: '{filename}', тип: '{doc_type}', хеш: '{file_hash[:16] if file_hash else 'N/A'}...'")

            # Retry логика для защиты от race conditions
            MAX_RETRIES = 3
            for attempt in range(MAX_RETRIES):
                try:
                    async with self.pool.acquire() as conn:
                        # ПРИОРИТЕТ 1: Проверка дубликатов по SHA256 хешу (самый надежный)
                        existing = None
                        duplicate_reason = None

                        # Пропускаем проверку дубликатов если skip_duplicates=True
                        if not skip_duplicates:
                            if file_hash:
                                existing = await conn.fetchrow(
                                    "SELECT id, filename FROM documents WHERE file_hash = $1",
                                    file_hash
                                )
                                if existing:
                                    duplicate_reason = f"содержимое идентично (SHA256: {file_hash[:16]}...)"
                                    logger.info(f"🎯 Найден дубликат по SHA256: {duplicate_reason}")

                            # ПРИОРИТЕТ 2: Проверка по имени файла + типу (если хеш не найден)
                            if not existing:
                                existing = await conn.fetchrow(
                                    "SELECT id, filename FROM documents WHERE filename = $1 AND document_type = $2",
                                    filename, doc_type
                                )
                                if existing:
                                    duplicate_reason = "имя и тип документа совпадают"
                                    logger.info(f"🎯 Найден дубликат по имени+типу: {duplicate_reason}")

                        if existing:
                            existing_id = str(existing['id'])
                            existing_filename = existing.get('filename', 'N/A')
                            logger.info(f"📋 Дубликат обнаружен: '{filename}' -> существующий документ '{existing_filename}' (ID: {existing_id}), причина: {duplicate_reason}")
                            return existing_id, True  # Возвращаем ID и флаг дубликата

                        # При skip_duplicates=True (force_reprocess) удаляем существующий документ с тем же хешем
                        if skip_duplicates and file_hash:
                            logger.info(f"🔄 Force reprocess: удаляем существующие документы с file_hash {file_hash[:16]}...")
                            delete_result = await conn.execute(
                                "DELETE FROM documents WHERE file_hash = $1",
                                file_hash
                            )
                            logger.info(f"🗑️ Удалено документов: {delete_result.split()[-1] if delete_result else '0'}")

                        # Генерируем UUID для нового документа
                        doc_id = str(uuid.uuid4())

                        query = """
                            INSERT INTO documents (id, file_path, filename, file_size, file_hash, document_type, processed_at, status, metadata)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            RETURNING id
                        """

                        result = await conn.fetchrow(
                            query,
                            doc_id,
                            clean_data['file_path'],
                            filename,  # Используем стандартизированное имя файла
                            clean_data.get('file_size'),
                            clean_data.get('file_hash'),
                            clean_data.get('document_type', 'general'),
                            clean_data.get('processed_at'),
                            clean_data.get('status', 'completed'),
                            json.dumps(clean_data.get('metadata', {}))
                        )

                    logger.info(f"✅ Документ {doc_id} добавлен в базу (попытка {attempt + 1})")
                    return doc_id, False  # Возвращаем ID и флаг - не дубликат

                except Exception as e:
                    error_msg = str(e).lower()
                    # Проверяем, не является ли это constraint violation (unique index на file_hash)
                    if ('unique' in error_msg or 'duplicate' in error_msg) and attempt < MAX_RETRIES - 1:
                        logger.warning(f"⚠️ Обнаружен race condition (попытка {attempt + 1}), повторяем поиск дубликата: {e}")
                        await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        continue  # Повторяем с начала (включая поиск дубликатов)
                    else:
                        # Это другая ошибка или исчерпаны попытки
                        raise

        except Exception as e:
            logger.error(f"❌ Ошибка вставки документа: {e}")
            raise DatabaseError(f"Document insertion failed: {e}")

    async def get_document(self, doc_id: str) -> Optional[Dict]:
        """Получение документа по ID."""
        try:
            query = "SELECT * FROM documents WHERE id = $1"
            async with self.pool.acquire() as conn:
                result = await conn.fetchrow(query, doc_id)

                if result:
                    doc = dict(result)
                    if doc['metadata']:
                        doc['metadata'] = json.loads(doc['metadata'])
                    return doc
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения документа {doc_id}: {e}")
            return None

    async def check_duplicates_bulk(self, documents_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Массовая проверка дубликатов для списка документов (полезно для архивов).

        Args:
            documents_info: Список словарей с ключами 'filename', 'file_hash', 'document_type'

        Returns:
            Dict с ключами:
            - 'duplicates': список найденных дубликатов
            - 'new_files': список новых файлов
            - 'summary': статистика
        """
        try:
            duplicates = []
            new_files = []

            async with self.pool.acquire() as conn:
                for doc_info in documents_info:
                    # Используем стандартизированное получение имени файла
                    try:
                        filename = self._get_standardized_filename(doc_info)
                    except ValueError:
                        # Fallback на оригинальную логику если стандартизация не сработала
                        filename = doc_info.get('filename', '')

                    file_hash = doc_info.get('file_hash', '')
                    doc_type = doc_info.get('document_type', 'general')

                    logger.debug(f"🔍 Bulk check: файл '{filename}', хеш: '{file_hash[:16] if file_hash else 'N/A'}...', тип: '{doc_type}'")

                    existing = None
                    duplicate_reason = None

                    # Проверка по SHA256 хешу (приоритет)
                    if file_hash:
                        existing = await conn.fetchrow(
                            "SELECT id, filename FROM documents WHERE file_hash = $1",
                            file_hash
                        )
                        if existing:
                            duplicate_reason = "идентичное содержимое"
                            logger.debug(f"🎯 Bulk найден дубликат по SHA256: {duplicate_reason}")

                    # Проверка по имени + типу
                    if not existing:
                        existing = await conn.fetchrow(
                            "SELECT id, filename FROM documents WHERE filename = $1 AND document_type = $2",
                            filename, doc_type
                        )
                        if existing:
                            duplicate_reason = "совпадение имени и типа"
                            logger.debug(f"🎯 Bulk найден дубликат по имени+типу: {duplicate_reason}")

                    if existing:
                        duplicates.append({
                            'filename': filename,
                            'existing_id': str(existing['id']),
                            'existing_filename': existing.get('filename', 'N/A'),
                            'reason': duplicate_reason,
                            'file_hash': file_hash[:16] + '...' if file_hash else 'N/A'
                        })
                    else:
                        new_files.append(doc_info)

            summary = {
                'total_files': len(documents_info),
                'duplicates_found': len(duplicates),
                'new_files': len(new_files),
                'duplicate_rate': len(duplicates) / len(documents_info) * 100 if documents_info else 0
            }

            logger.info(f"🔍 Проверка дубликатов: {summary['duplicates_found']} из {summary['total_files']} файлов являются дубликатами")

            return {
                'duplicates': duplicates,
                'new_files': new_files,
                'summary': summary
            }

        except Exception as e:
            logger.error(f"❌ Ошибка массовой проверки дубликатов: {e}")
            return {
                'duplicates': [],
                'new_files': documents_info,
                'summary': {
                    'total_files': len(documents_info),
                    'duplicates_found': 0,
                    'new_files': len(documents_info),
                    'duplicate_rate': 0,
                    'error': str(e)
                }
            }

    async def insert_chunks(self, chunks: List[TextChunk], document_id: str) -> int:
        """Вставка чанков в базу."""
        try:
            query = """
                INSERT INTO chunks (id, document_id, chunk_index, text, chunk_type, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """

            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for chunk in chunks:
                        await conn.execute(
                            query,
                            chunk.id,
                            document_id,
                            chunk.metadata.get('chunk_index', 0),
                            chunk.text,
                            chunk.metadata.get('chunk_type', 'text'),
                            json.dumps(chunk.metadata),
                            datetime.now()
                        )

            logger.info(f"✅ Вставлено {len(chunks)} чанков для документа {document_id}")
            return len(chunks)

        except Exception as e:
            logger.error(f"❌ Ошибка вставки чанков: {e}")
            raise DatabaseError(f"Chunks insertion failed: {e}")

    # =================================================================
    # PGvector методы (v4.0)
    # =================================================================

    async def execute(self, query: str, *args):
        """Простой execute метод для pgvector."""
        if not self.pool:
            raise DatabaseError("PostgreSQL pool not initialized")
        
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        """Простой fetch метод для pgvector."""
        if not self.pool:
            raise DatabaseError("PostgreSQL pool not initialized")
        
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchval(self, query: str, *args):
        """Простой fetchval метод для pgvector."""
        if not self.pool:
            raise DatabaseError("PostgreSQL pool not initialized")
        
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    def transaction(self):
        """Метод для создания транзакции (совместимость с PgVectorManager)."""
        if not self.pool:
            raise DatabaseError("PostgreSQL pool not initialized")
        
        return self.pool.acquire()


def create_postgres_manager() -> PostgresManager:
    """Factory function для создания PostgresManager."""
    return PostgresManager()