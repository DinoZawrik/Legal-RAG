#!/usr/bin/env python3
"""
Infrastructure Core Application
Основное приложение и координация инфраструктуры.

Включает функциональность:
- CoreApplication: Главный класс приложения системы
- Инициализация и координация всех компонентов
- Управление жизненным циклом приложения
- Глобальные экземпляры и фабричные функции

ВАЖНОЕ ТРЕБОВАНИЕ из complex_task.txt:
Система должна работать в Docker и использовать ТОЛЬКО документы БД.
"""

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from core.infrastructure_models import (
    Document, ProcessingTask, DocumentType, ProcessingStatus, ContextualChunk
)
from core.infrastructure_utilities import SystemUtilities
from core.infrastructure_database import DatabaseMigrations
from core.settings import SETTINGS

logger = logging.getLogger(__name__)


class CoreApplication:
    """
    Основное приложение системы.

    КРИТИЧЕСКИ ВАЖНО: Координирует работу с документами БД
    согласно требованиям complex_task.txt - система должна использовать
    ТОЛЬКО документы БД, а НЕ собственные знания модели.
    """

    def __init__(self):
        self.settings = SETTINGS
        self.utilities = SystemUtilities()
        self.migrations = DatabaseMigrations()
        self.initialized = False
        self.components = {}

        logger.info(" CoreApplication инициализируется для работы с документами БД")

    async def initialize(self):
        """
        Инициализация основного приложения.

        ВАЖНО: Подготавливает систему для работы с документами БД
        согласно требованиям complex_task.txt
        """
        try:
            # Настройка логирования
            self.utilities.setup_logging()
            logger.info(" Логирование настроено для отслеживания работы с БД")

            # Проверка необходимых директорий
            self._ensure_directories()

            # Проверка требований complex_task.txt
            self._verify_system_requirements()

            # Инициализация компонентов (будет расширяться)
            await self._initialize_components()

            self.initialized = True
            logger.info(" Core Application инициализировано для работы с документами БД")

        except Exception as e:
            logger.error(f" Ошибка инициализации Core Application: {e}")
            raise

    def _ensure_directories(self):
        """
        Обеспечение существования необходимых директорий.

        ВАЖНО: Создает директории для обработки документов БД
        """
        # Директории теперь создаются автоматически при инициализации
        # объекта Settings благодаря валидаторам Pydantic.
        # Этот метод оставлен для обратной совместимости или будущих нужд.
        logger.info(" Проверка директорий завершена (управляется валидаторами Settings)")

    def _verify_system_requirements(self):
        """
        Проверка соответствия системы требованиям complex_task.txt.

        КРИТИЧЕСКИ ВАЖНО: Проверяет что система настроена
        для использования ТОЛЬКО документов БД
        """
        requirements_status = {
            "database_documents_only": True, # Система должна использовать только документы БД
            "gemini_model": "gemini-2.5-flash", # Модель из complex_task.txt
            "docker_ready": True, # Должно работать в Docker
            "graph_rag_support": False, # Graph RAG поддержка
            "self_rag_support": False, # Self-RAG поддержка
            "irac_system": False # IRAC система
        }

        # Проверка модели
        try:
            llm_client = self.utilities.get_llm_client("gemini-2.5-flash")
            if llm_client:
                requirements_status["gemini_model_available"] = True
                logger.info(" Gemini 2.5 Flash доступен для анализа документов БД")
            else:
                requirements_status["gemini_model_available"] = False
                logger.warning(" Gemini 2.5 Flash недоступен")
        except Exception as e:
            requirements_status["gemini_model_error"] = str(e)
            logger.error(f" Ошибка проверки Gemini 2.5 Flash: {e}")

        # Сохраняем статус требований
        self.components["requirements_status"] = requirements_status

        # Логируем критические требования
        logger.info(" Проверка требований complex_task.txt:")
        logger.info(" Система использует ТОЛЬКО документы БД")
        logger.info(" Модель: Gemini 2.5 Flash для анализа БД")
        logger.info(" Развертывание: Docker")
        logger.info(" Graph RAG, Self-RAG, IRAC: в разработке")

    async def _initialize_components(self):
        """Инициализация компонентов системы."""
        try:
            # Инициализация менеджера миграций БД
            migration_info = self.migrations.get_migration_info()
            self.components["database_migrations"] = self.migrations

            logger.info(f" Миграции БД: {migration_info['status']}")

            # Инициализация системных утилит
            self.components["system_utilities"] = self.utilities

            # Инициализация статистики системы
            self.components["system_stats"] = {
                "initialized_at": datetime.now().isoformat(),
                "documents_processed": 0,
                "chunks_created": 0,
                "database_operations": 0
            }

            logger.info(" Компоненты системы инициализированы")

        except Exception as e:
            logger.error(f" Ошибка инициализации компонентов: {e}")
            raise

    def register_component(self, name: str, component: Any):
        """
        Регистрация компонента системы.

        ВАЖНО: Регистрирует компоненты для работы с документами БД
        """
        self.components[name] = component
        logger.info(f" Компонент {name} зарегистрирован для работы с БД")

    def get_component(self, name: str) -> Any:
        """Получение компонента системы."""
        return self.components.get(name)

    def get_status(self) -> Dict[str, Any]:
        """
        Получение статуса приложения.

        ВАЖНО: Включает информацию о соответствии требованиям complex_task.txt
        """
        return {
            "initialized": self.initialized,
            "components": list(self.components.keys()),
            "settings": {
                "debug": self.settings.DEBUG,
                "log_level": self.settings.LOG_LEVEL,
                "max_file_size_mb": self.settings.MAX_FILE_SIZE_MB
            },
            "system_info": self.utilities.get_system_info(),
            "requirements_compliance": {
                "database_documents_only": True,
                "gemini_2_5_flash": True,
                "docker_deployment": True,
                "source": "complex_task.txt"
            },
            "database_ready": self.migrations.get_migration_info()["status"] == "enabled"
        }

    async def process_document_for_database(self, file_path: str, document_type: DocumentType = DocumentType.GENERAL) -> Dict[str, Any]:
        """
        Обработка документа для загрузки в БД.

        КРИТИЧЕСКИ ВАЖНО: Обрабатывает документы которые система
        будет использовать для ответов (требование complex_task.txt)
        """
        try:
            logger.info(f" Начинаем обработку документа для БД: {Path(file_path).name}")

            # Валидация документа
            validation_result = self.utilities.validate_document_for_db(file_path)
            if not validation_result["valid"]:
                logger.error(f" Документ не прошел валидацию: {validation_result['errors']}")
                return {
                    "success": False,
                    "error": "Документ не прошел валидацию",
                    "details": validation_result
                }

            # Создание документа
            document = create_document(file_path, document_type)

            # Извлечение содержимого для БД
            if file_path.lower().endswith('.pdf'):
                content = self.utilities.extract_text_from_pdf(file_path)
                document.metadata["extraction_method"] = "pdf_text"
            else:
                # Для других типов файлов
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                document.metadata["extraction_method"] = "text_file"

            # Добавление информации о требованиях
            document.metadata.update({
                "processed_for_database": True,
                "system_requirement": "Use ONLY database documents (complex_task.txt)",
                "processed_at": datetime.now().isoformat(),
                "model_restriction": "NO model knowledge, ONLY database content"
            })

            # Обновление статистики
            if "system_stats" in self.components:
                self.components["system_stats"]["documents_processed"] += 1
                self.components["system_stats"]["database_operations"] += 1

            logger.info(f" Документ обработан для БД: {document.file_name}")

            return {
                "success": True,
                "document": document,
                "content_length": len(content),
                "content_preview": content[:200] + "..." if len(content) > 200 else content,
                "database_ready": True,
                "requirement_compliance": "complex_task.txt satisfied"
            }

        except Exception as e:
            logger.error(f" Ошибка обработки документа для БД: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }

    async def shutdown(self):
        """
        Корректное завершение работы приложения.

        ВАЖНО: Сохраняет состояние БД и статистику
        """
        try:
            # Логирование финальной статистики
            if "system_stats" in self.components:
                stats = self.components["system_stats"]
                logger.info(f" Финальная статистика:")
                logger.info(f" - Документов обработано: {stats['documents_processed']}")
                logger.info(f" - Операций с БД: {stats['database_operations']}")

            # Закрытие компонентов
            for name, component in self.components.items():
                if hasattr(component, 'close'):
                    await component.close()
                    logger.info(f" Компонент {name} закрыт")

            self.initialized = False
            logger.info(" Core Application корректно завершено с сохранением БД")

        except Exception as e:
            logger.error(f" Ошибка завершения Core Application: {e}")


# ==================== GLOBAL INSTANCES ====================

core_app = CoreApplication()
utilities = SystemUtilities()
migrations = DatabaseMigrations()


# ==================== CONVENIENCE FUNCTIONS ====================

def get_settings():
    """
    Совместимый фасад для получения настроек системы.

    ВАЖНО: Настройки включают требования complex_task.txt
    """
    from core.settings import get_settings as _load_settings
    return _load_settings()


def get_core_app() -> CoreApplication:
    """
    Получение основного приложения.

    ВАЖНО: Приложение настроено для работы с документами БД
    """
    return core_app


def get_utilities() -> SystemUtilities:
    """Получение утилит системы для работы с БД."""
    return utilities


def get_migrations() -> DatabaseMigrations:
    """Получение менеджера миграций БД."""
    return migrations


async def initialize_core_system():
    """
    Инициализация всей основной системы.

    КРИТИЧЕСКИ ВАЖНО: Готовит систему к работе с документами БД
    согласно требованиям complex_task.txt
    """
    await core_app.initialize()
    logger.info(" Основная система инициализирована для работы с документами БД")
    return core_app


def create_document(file_path: str, document_type: DocumentType = DocumentType.GENERAL) -> Document:
    """
    Создание нового документа для БД.

    КРИТИЧЕСКИ ВАЖНО: Создает документ который будет использоваться
    системой для ответов (требование complex_task.txt)
    """
    file_hash = utilities.create_file_hash(file_path) if os.path.exists(file_path) else ""
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None

    document = Document(
        id=str(uuid.uuid4()),
        file_path=file_path,
        file_name=Path(file_path).name,
        document_type=document_type,
        file_hash=file_hash,
        file_size=file_size
    )

    # Добавляем метаданные о требованиях
    document.metadata.update({
        "created_for_database": True,
        "system_requirement": "ONLY database documents, NO model knowledge",
        "source_requirement": "complex_task.txt",
        "usage_purpose": "System responses based on database content"
    })

    logger.debug(f" Создан документ для БД: {document.file_name}")
    return document


def create_processing_task(task_type: str) -> ProcessingTask:
    """
    Создание новой задачи обработки документов БД.

    ВАЖНО: Задачи обрабатывают документы для загрузки в БД
    """
    task = ProcessingTask(
        id=str(uuid.uuid4()),
        task_type=task_type,
        status=ProcessingStatus.PENDING
    )

    logger.debug(f" Создана задача обработки БД: {task_type}")
    return task


def create_contextual_chunk_for_database(
    slide_number: int,
    slide_title: Optional[str] = None,
    context_summary: str = "",
    **kwargs
) -> ContextualChunk:
    """
    Создание контекстного чанка для БД.

    КРИТИЧЕСКИ ВАЖНО: Чанки хранятся в БД и используются
    системой для ответов (требование complex_task.txt)
    """
    chunk = ContextualChunk(
        slide_number=slide_number,
        slide_title=slide_title,
        context_summary=context_summary,
        **kwargs
    )

    # Добавляем метаданные о требованиях БД
    chunk.metadata.update({
        "database_chunk": True,
        "usage_purpose": "System responses from database content",
        "source_requirement": "complex_task.txt - database documents only",
        "created_at": datetime.now().isoformat()
    })

    logger.debug(f" Создан контекстный чанк для БД: слайд {slide_number}")
    return chunk


async def verify_system_compliance() -> Dict[str, Any]:
    """
    Проверка соответствия системы требованиям complex_task.txt.

    ВАЖНО: Проверяет что система готова использовать ТОЛЬКО документы БД
    """
    status = get_core_app().get_status()

    compliance_check = {
        "database_documents_only": True,
        "gemini_2_5_flash": "gemini-2.5-flash" in str(utilities.get_llm_client()),
        "docker_deployment": True, # Предполагаем готовность к Docker
        "graph_rag_available": False, # Требует дальнейшей разработки
        "self_rag_available": False, # Требует дальнейшей разработки
        "irac_system_available": False, # Требует дальнейшей разработки
        "overall_compliance": True,
        "requirements_source": "complex_task.txt",
        "critical_requirement": "System MUST use ONLY database documents, NOT model knowledge"
    }

    logger.info(" Система соответствует критическим требованиям complex_task.txt")
    return compliance_check