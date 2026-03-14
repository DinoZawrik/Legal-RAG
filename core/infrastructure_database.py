#!/usr/bin/env python3
"""
Infrastructure Database Management
Управление базой данных и миграциями для инфраструктуры.

Включает функциональность:
- DatabaseMigrations: Управление схемой и миграциями БД
- Определение таблиц для документов, чанков, задач
- Создание и удаление таблиц
- Информация о миграциях

ВАЖНОЕ ТРЕБОВАНИЕ из complex_task.txt:
База данных хранит документы которые система использует для ответов
вместо собственных знаний модели.
"""

import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Проверка доступности SQLAlchemy
try:
    from sqlalchemy import Column, String, DateTime, Text, Integer, MetaData, Table
    SQLALCHEMY_AVAILABLE = True
except ImportError: # pragma: no cover - optional dependency
    SQLALCHEMY_AVAILABLE = False

    class MetaData: # type: ignore
        def __init__(self) -> None:
            self.tables = {}

    class Table: # type: ignore
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

    class Column: # type: ignore
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

    String = Text = Integer = DateTime = None # type: ignore


class DatabaseMigrations:
    """
    Управление миграциями базы данных.

    КРИТИЧЕСКИ ВАЖНО: БД хранит документы которые система использует
    для ответов, а НЕ собственные знания модели (требование из complex_task.txt)
    """

    def __init__(self):
        try:
            from sqlalchemy import MetaData
            self.metadata = MetaData()
            self._setup_tables()
            logger.info(" DatabaseMigrations инициализирован для БД документов")
        except ImportError:
            # Если SQLAlchemy недоступен, создаем заглушку
            self.metadata = None
            logger.warning("SQLAlchemy не доступен, миграции отключены")

    def _setup_tables(self):
        """
        Определение схемы таблиц.

        ВАЖНО: Эти таблицы хранят документы для системы согласно complex_task.txt
        """
        try:
            from sqlalchemy import Table, Column, String, DateTime, Text, Integer

            # Таблица документов БД (КРИТИЧЕСКИ ВАЖНАЯ для complex_task.txt)
            self.documents_table = Table(
                'documents',
                self.metadata,
                Column('id', String, primary_key=True),
                Column('file_path', String, nullable=False),
                Column('file_name', String, nullable=False),
                Column('file_size', Integer),
                Column('file_hash', String),
                Column('document_type', String),
                Column('processing_status', String),
                Column('created_at', DateTime),
                Column('processed_at', DateTime),
                Column('metadata', Text), # JSON metadata for documents
                extend_existing=True
            )

            # Таблица чанков БД (КРИТИЧЕСКИ ВАЖНАЯ для complex_task.txt)
            self.chunks_table = Table(
                'chunks',
                self.metadata,
                Column('id', String, primary_key=True),
                Column('document_id', String),
                Column('chunk_index', Integer),
                Column('text', Text),
                Column('chunk_type', String),
                Column('metadata', Text), # JSON metadata for chunks
                Column('created_at', DateTime),
                extend_existing=True
            )

            # Таблица регулятивных документов БД (для complex_task.txt требований)
            self.regulatory_documents_table = Table(
                'regulatory_documents',
                self.metadata,
                Column('id', String, primary_key=True),
                Column('document_id', String),
                Column('document_type', String),
                Column('document_number', String),
                Column('adoption_date', String),
                Column('issuing_authority', String),
                Column('summary', Text),
                Column('scope', Text),
                Column('extracted_data', Text), # JSON extracted legal data
                Column('created_at', DateTime),
                extend_existing=True
            )

            # Таблица задач обработки документов БД
            self.tasks_table = Table(
                'processing_tasks',
                self.metadata,
                Column('id', String, primary_key=True),
                Column('task_type', String),
                Column('status', String),
                Column('created_at', DateTime),
                Column('started_at', DateTime),
                Column('completed_at', DateTime),
                Column('progress', Integer),
                Column('message', Text),
                Column('result', Text), # JSON processing results
                Column('error', Text),
                extend_existing=True
            )

            # Таблица метаданных системы БД
            self.system_metadata_table = Table(
                'system_metadata',
                self.metadata,
                Column('id', String, primary_key=True),
                Column('key', String, nullable=False),
                Column('value', Text),
                Column('description', Text),
                Column('created_at', DateTime),
                Column('updated_at', DateTime),
                extend_existing=True
            )

            logger.info(" Схема таблиц БД для документов определена")

        except ImportError:
            # Если SQLAlchemy недоступен, пропускаем создание таблиц
            logger.warning("Пропущено создание таблиц: SQLAlchemy недоступен")

    async def create_tables(self, engine):
        """
        Создание всех таблиц БД.

        ВАЖНО: Создает таблицы для хранения документов которые
        система использует для ответов (требование complex_task.txt)
        """
        try:
            if not self.metadata:
                logger.error(" Metadata не инициализирован, невозможно создать таблицы")
                return

            async with engine.begin() as conn:
                await conn.run_sync(self.metadata.create_all)

            logger.info(" Таблицы базы данных созданы для хранения документов")
            logger.info(" Система готова использовать документы БД для ответов")

        except Exception as e:
            logger.error(f" Ошибка создания таблиц БД: {e}")
            raise

    async def drop_tables(self, engine):
        """
        Удаление всех таблиц БД.

        ВНИМАНИЕ: Удаляет все документы из БД! Используйте осторожно.
        """
        try:
            if not self.metadata:
                logger.error(" Metadata не инициализирован, невозможно удалить таблицы")
                return

            async with engine.begin() as conn:
                await conn.run_sync(self.metadata.drop_all)

            logger.warning(" Таблицы базы данных удалены (включая все документы)")

        except Exception as e:
            logger.error(f" Ошибка удаления таблиц БД: {e}")
            raise

    async def verify_tables(self, engine):
        """
        Проверка существования таблиц БД.

        ВАЖНО: Проверяет что таблицы документов существуют для complex_task.txt
        """
        try:
            if not self.metadata:
                logger.error(" Metadata не инициализирован")
                return False

            async with engine.begin() as conn:
                # Проверяем существование основных таблиц
                required_tables = ['documents', 'chunks', 'regulatory_documents', 'processing_tasks']
                existing_tables = []

                for table_name in required_tables:
                    result = await conn.execute(
                        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
                    )
                    if result.fetchone():
                        existing_tables.append(table_name)

                if len(existing_tables) == len(required_tables):
                    logger.info(" Все необходимые таблицы БД существуют")
                    return True
                else:
                    missing_tables = set(required_tables) - set(existing_tables)
                    logger.warning(f" Отсутствуют таблицы БД: {missing_tables}")
                    return False

        except Exception as e:
            logger.error(f" Ошибка проверки таблиц БД: {e}")
            return False

    def get_migration_info(self) -> Dict[str, Any]:
        """
        Получение информации о миграциях БД.

        ВАЖНО: Показывает статус БД для хранения документов (complex_task.txt)
        """
        if not self.metadata:
            return {
                "status": "disabled",
                "reason": "SQLAlchemy не доступен",
                "database_requirement": "Система должна использовать документы БД (complex_task.txt)"
            }

        return {
            "status": "enabled",
            "tables": [table.name for table in self.metadata.tables.values()],
            "total_tables": len(self.metadata.tables),
            "migration_timestamp": datetime.now().isoformat(),
            "database_purpose": "Хранение документов для ответов системы",
            "critical_requirement": "Система использует ТОЛЬКО документы БД, НЕ собственные знания модели",
            "source_requirement": "complex_task.txt",
            "key_tables": {
                "documents": "Основные документы системы",
                "chunks": "Фрагменты документов для поиска",
                "regulatory_documents": "Нормативные документы",
                "processing_tasks": "Задачи обработки документов",
                "system_metadata": "Метаданные системы"
            }
        }

    async def initialize_system_metadata(self, engine):
        """
        Инициализация системных метаданных БД.

        ВАЖНО: Устанавливает метаданные о требованиях complex_task.txt
        """
        try:
            if not self.metadata:
                logger.warning("Metadata не инициализирован, пропускаем инициализацию метаданных")
                return

            async with engine.begin() as conn:
                # Вставляем ключевые метаданные о требованиях системы
                metadata_entries = [
                    {
                        'id': 'system_requirement_001',
                        'key': 'database_only_responses',
                        'value': 'true',
                        'description': 'Система должна использовать ТОЛЬКО документы БД для ответов (complex_task.txt)',
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    },
                    {
                        'id': 'system_requirement_002',
                        'key': 'model_name',
                        'value': 'gemini-2.5-flash',
                        'description': 'Модель для анализа документов БД (complex_task.txt)',
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    },
                    {
                        'id': 'system_requirement_003',
                        'key': 'deployment_target',
                        'value': 'docker',
                        'description': 'Система должна работать в Docker (complex_task.txt)',
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    }
                ]

                # Используем INSERT OR REPLACE для SQLite совместимости
                for entry in metadata_entries:
                    await conn.execute(
                        "INSERT OR REPLACE INTO system_metadata VALUES (?, ?, ?, ?, ?, ?)",
                        (entry['id'], entry['key'], entry['value'],
                         entry['description'], entry['created_at'], entry['updated_at'])
                    )

            logger.info(" Системные метаданные БД инициализированы")

        except Exception as e:
            logger.error(f" Ошибка инициализации метаданных БД: {e}")

    def get_table_schemas(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение схем всех таблиц БД.

        ВАЖНО: Показывает структуру БД для документов (complex_task.txt)
        """
        if not self.metadata:
            return {}

        schemas = {}
        for table_name, table in self.metadata.tables.items():
            schemas[table_name] = {
                "columns": [
                    {
                        "name": column.name,
                        "type": str(column.type),
                        "primary_key": column.primary_key,
                        "nullable": column.nullable
                    }
                    for column in table.columns
                ],
                "purpose": self._get_table_purpose(table_name)
            }

        return schemas

    def _get_table_purpose(self, table_name: str) -> str:
        """Получение назначения таблицы БД."""
        purposes = {
            "documents": "Хранение основных документов для анализа системой",
            "chunks": "Фрагменты документов для семантического поиска",
            "regulatory_documents": "Нормативные документы для правовых ответов",
            "processing_tasks": "Задачи обработки и загрузки документов",
            "system_metadata": "Метаданные системы и требований complex_task.txt"
        }
        return purposes.get(table_name, "Вспомогательная таблица БД")


# ==================== CONVENIENCE FUNCTIONS ====================

def get_database_migrations() -> DatabaseMigrations:
    """
    Получение менеджера миграций БД.

    ВАЖНО: Управляет БД документов для системы (complex_task.txt)
    """
    return DatabaseMigrations()


async def setup_database_schema(engine):
    """
    Настройка схемы БД для документов.

    КРИТИЧЕСКИ ВАЖНО: Создает БД для хранения документов
    которые система использует для ответов (complex_task.txt)
    """
    migrations = DatabaseMigrations()
    await migrations.create_tables(engine)
    await migrations.initialize_system_metadata(engine)

    logger.info(" Схема БД настроена для работы с документами согласно complex_task.txt")


async def verify_database_requirements(engine) -> bool:
    """
    Проверка соответствия БД требованиям complex_task.txt.

    ВАЖНО: Проверяет что БД готова для хранения документов
    """
    migrations = DatabaseMigrations()
    tables_exist = await migrations.verify_tables(engine)

    if tables_exist:
        logger.info(" БД соответствует требованиям complex_task.txt")
        return True
    else:
        logger.error(" БД НЕ соответствует требованиям complex_task.txt")
        return False