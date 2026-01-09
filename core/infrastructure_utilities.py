#!/usr/bin/env python3
"""
🔧 Infrastructure System Utilities
Системные утилиты для инфраструктуры.

Включает функциональность:
- SystemUtilities: PDF обработка, валидация файлов, LLM клиент
- Логирование и системная информация
- Работа с файлами и хешированием
- Интеграция с Google Gemini 2.5 Flash

ВАЖНОЕ ТРЕБОВАНИЕ из complex_task.txt:
Система использует модель Gemini 2.5 Flash для анализа документов БД.
"""

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Import settings
from core.settings import SETTINGS

logger = logging.getLogger(__name__)


class SystemUtilities:
    """
    Системные утилиты.
    Объединяет функциональность работы с файлами, PDF, LLM и системой.

    КРИТИЧЕСКИ ВАЖНО: LLM используется для анализа документов БД,
    а НЕ для ответов на основе собственных знаний (требование из complex_task.txt)
    """

    @staticmethod
    def get_llm_client(model_name: str = "gemini-2.5-flash"):
        """
        Получение клиента LLM.

        ВАЖНО: Используется модель Gemini 2.5 Flash согласно complex_task.txt
        для анализа документов БД, а НЕ для ответов на основе собственных знаний.
        """
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            # Попытка получить API ключ разными способами
            api_key = None

            # Безопасное извлечение GOOGLE_API_KEY
            if hasattr(SETTINGS, 'GOOGLE_API_KEY') and SETTINGS.GOOGLE_API_KEY:
                if hasattr(SETTINGS.GOOGLE_API_KEY, 'get_secret_value'):
                    api_key = SETTINGS.GOOGLE_API_KEY.get_secret_value()
                else:
                    # Fallback для строкового значения
                    api_key = str(SETTINGS.GOOGLE_API_KEY) if SETTINGS.GOOGLE_API_KEY else None

            # Fallback на GEMINI_API_KEY
            if not api_key and hasattr(SETTINGS, 'GEMINI_API_KEY') and SETTINGS.GEMINI_API_KEY:
                if hasattr(SETTINGS.GEMINI_API_KEY, 'get_secret_value'):
                    api_key = SETTINGS.GEMINI_API_KEY.get_secret_value()
                else:
                    # Fallback для строкового значения
                    api_key = str(SETTINGS.GEMINI_API_KEY) if SETTINGS.GEMINI_API_KEY else None

            # Fallback на переменные окружения
            if not api_key:
                import os
                api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

            if not api_key:
                logger.warning("Google API ключ не найден. LLM клиент может не работать.")

            logger.info(f"🤖 Инициализация {model_name} для анализа документов БД")
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=0.7,
                max_tokens=4000
            )
        except ImportError:
            logger.warning("LangChain не доступен")
            return None
        except Exception as e:
            logger.error(f"Ошибка создания LLM клиента: {e}")
            return None

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """
        Извлечение текста из PDF (совместимость).

        ВАЖНО: Извлекает текст для загрузки в БД согласно требованиям complex_task.txt
        """
        pages = SystemUtilities.extract_text_from_pdf_pages(file_path)
        return "\n\n".join([page["text"] for page in pages])

    @staticmethod
    def extract_text_from_pdf_pages(file_path: str) -> List[Dict[str, Any]]:
        """
        Извлечение текста из PDF постранично с нормализацией.

        ВАЖНО: Извлеченный текст загружается в БД для последующего использования
        системой вместо собственных знаний модели (требование из complex_task.txt)

        УЛУЧШЕНИЕ: Добавлена нормализация текста для удаления переносов в терминах
        """
        try:
            import fitz  # PyMuPDF
            from core.text_normalization import normalize_legal_text

            logger.info(f"📄 Начинаем извлечение текста из PDF для загрузки в БД: {file_path}")

            # Простое и надежное открытие файла как в v1.0
            doc = fitz.open(file_path)
            pages = []
            total_pages = len(doc)

            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                raw_text = page.get_text()

                # КРИТИЧНО: Нормализуем текст для удаления переносов в юридических терминах
                # Решает проблему: "плата \nконцедента" → "плата концедента"
                normalized_text = normalize_legal_text(raw_text)

                # Получаем дополнительную информацию о странице
                page_info = {
                    "page_number": page_num + 1,
                    "total_pages": total_pages,
                    "text": normalized_text,  # ИСПОЛЬЗУЕМ НОРМАЛИЗОВАННЫЙ ТЕКСТ
                    "text_length": len(normalized_text.strip()),
                    "has_content": bool(normalized_text.strip()),
                    "metadata": {
                        "page_size": page.rect,
                        "rotation": page.rotation,
                        "mediabox": page.mediabox,
                        "source": "database_document",  # Указываем что это для БД
                        "text_normalized": True  # Флаг что текст нормализован
                    }
                }
                pages.append(page_info)

            doc.close()
            logger.info(f"📄 Извлечено и нормализовано {total_pages} страниц из {Path(file_path).name} для БД")
            return pages

        except ImportError:
            logger.error("PyMuPDF не установлен")
            return []
        except Exception as e:
            logger.error(f"Ошибка извлечения текста из PDF {file_path}: {e}")
            return []

    @staticmethod
    def validate_file_type(file_path: str) -> bool:
        """
        Проверка типа файла.

        ВАЖНО: Валидирует файлы перед загрузкой в БД
        """
        file_ext = Path(file_path).suffix.lower()
        return file_ext in SETTINGS.SUPPORTED_FILE_TYPES

    @staticmethod
    def validate_file_size(file_path: str) -> bool:
        """
        Проверка размера файла.

        ВАЖНО: Ограничивает размер файлов для загрузки в БД
        """
        try:
            file_size = os.path.getsize(file_path)
            max_size = SETTINGS.MAX_FILE_SIZE_MB * 1024 * 1024  # Конвертация в байты
            return file_size <= max_size
        except Exception:
            return False

    @staticmethod
    def create_file_hash(file_path: str) -> str:
        """
        Создание хеша файла.

        ВАЖНО: Хеш используется для предотвращения дублирования в БД
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.error(f"Ошибка создания хеша файла {file_path}: {e}")
            return ""

    @staticmethod
    def setup_logging(level: str = None):
        """
        Настройка логирования.

        ВАЖНО: Логирование помогает отслеживать работу с документами БД
        """
        log_level = level or SETTINGS.LOG_LEVEL

        try:
            from core.logging_config import configure_logging

            configure_logging(log_level)
        except ModuleNotFoundError:
            logging.basicConfig(
                level=getattr(logging, log_level.upper()),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler('legalrag_system.log', encoding='utf-8')
                ]
            )

        logger.info(f"📝 Логирование настроено на уровень {log_level}")

    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """
        Получение информации о системе.

        ВАЖНО: Системная информация для мониторинга работы с БД
        """
        import platform

        try:
            import psutil

            return {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total,
                "memory_available": psutil.virtual_memory().available,
                "disk_usage": psutil.disk_usage('/').percent,
                "timestamp": datetime.now().isoformat(),
                "database_requirement": "Система использует ТОЛЬКО документы БД (complex_task.txt)"
            }
        except ImportError:
            return {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "timestamp": datetime.now().isoformat(),
                "database_requirement": "Система использует ТОЛЬКО документы БД (complex_task.txt)"
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о системе: {e}")
            return {"error": str(e)}

    @staticmethod
    def validate_document_for_db(file_path: str) -> Dict[str, Any]:
        """
        Комплексная валидация документа перед загрузкой в БД.

        ВАЖНО: Проверяет документы согласно требованиям complex_task.txt
        """
        validation_result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "file_info": {}
        }

        try:
            # Проверка существования файла
            if not os.path.exists(file_path):
                validation_result["errors"].append("Файл не существует")
                return validation_result

            # Проверка типа файла
            if not SystemUtilities.validate_file_type(file_path):
                validation_result["errors"].append(f"Неподдерживаемый тип файла: {Path(file_path).suffix}")

            # Проверка размера файла
            if not SystemUtilities.validate_file_size(file_path):
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                validation_result["errors"].append(f"Файл слишком большой: {file_size_mb:.1f}MB > {SETTINGS.MAX_FILE_SIZE_MB}MB")

            # Получение информации о файле
            file_stats = os.stat(file_path)
            validation_result["file_info"] = {
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "file_size": file_stats.st_size,
                "file_hash": SystemUtilities.create_file_hash(file_path),
                "created_at": datetime.fromtimestamp(file_stats.st_ctime),
                "modified_at": datetime.fromtimestamp(file_stats.st_mtime),
                "extension": Path(file_path).suffix.lower(),
                "database_ready": len(validation_result["errors"]) == 0
            }

            # Если нет ошибок, файл готов для БД
            validation_result["valid"] = len(validation_result["errors"]) == 0

            if validation_result["valid"]:
                logger.info(f"✅ Файл {Path(file_path).name} готов для загрузки в БД")
            else:
                logger.warning(f"❌ Файл {Path(file_path).name} не прошел валидацию для БД")

        except Exception as e:
            validation_result["errors"].append(f"Ошибка валидации: {str(e)}")
            logger.error(f"Ошибка валидации файла {file_path}: {e}")

        return validation_result

    @staticmethod
    def extract_document_metadata(file_path: str) -> Dict[str, Any]:
        """
        Извлечение метаданных документа для БД.

        ВАЖНО: Метаданные сохраняются в БД согласно требованиям complex_task.txt
        """
        metadata = {
            "extraction_timestamp": datetime.now().isoformat(),
            "source_system": "LegalRAG Infrastructure",
            "document_source": "database_document",
            "processing_requirements": "Use ONLY database documents, NOT model knowledge"
        }

        try:
            file_path_obj = Path(file_path)
            file_stats = os.stat(file_path)

            # Основные метаданные файла
            metadata.update({
                "file_name": file_path_obj.name,
                "file_extension": file_path_obj.suffix.lower(),
                "file_size_bytes": file_stats.st_size,
                "file_size_mb": round(file_stats.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                "file_hash": SystemUtilities.create_file_hash(file_path)
            })

            # Специфичные метаданные для PDF
            if file_path_obj.suffix.lower() == '.pdf':
                try:
                    import fitz
                    doc = fitz.open(file_path)
                    pdf_metadata = doc.metadata

                    metadata.update({
                        "pdf_pages": len(doc),
                        "pdf_title": pdf_metadata.get("title", ""),
                        "pdf_author": pdf_metadata.get("author", ""),
                        "pdf_subject": pdf_metadata.get("subject", ""),
                        "pdf_creator": pdf_metadata.get("creator", ""),
                        "pdf_producer": pdf_metadata.get("producer", ""),
                        "pdf_creation_date": pdf_metadata.get("creationDate", ""),
                        "pdf_modification_date": pdf_metadata.get("modDate", "")
                    })
                    doc.close()
                except Exception as e:
                    metadata["pdf_extraction_error"] = str(e)

            logger.debug(f"📋 Извлечены метаданные для БД: {file_path_obj.name}")

        except Exception as e:
            metadata["extraction_error"] = str(e)
            logger.error(f"Ошибка извлечения метаданных {file_path}: {e}")

        return metadata


# ==================== CONVENIENCE FUNCTIONS ====================

def get_system_utilities() -> SystemUtilities:
    """Получение экземпляра системных утилит."""
    return SystemUtilities()


def validate_file_for_database(file_path: str) -> bool:
    """
    Быстрая проверка файла для БД.

    ВАЖНО: Проверяет готовность файла для загрузки в БД
    """
    utilities = SystemUtilities()
    return (utilities.validate_file_type(file_path) and
            utilities.validate_file_size(file_path))


def extract_pdf_content_for_database(file_path: str) -> str:
    """
    Извлечение содержимого PDF для загрузки в БД.

    КРИТИЧЕСКИ ВАЖНО: Содержимое будет использоваться системой
    для ответов, а НЕ собственные знания модели (complex_task.txt)
    """
    utilities = SystemUtilities()
    content = utilities.extract_text_from_pdf(file_path)

    if content:
        logger.info(f"📄 Извлечено {len(content)} символов из PDF для БД")
    else:
        logger.warning(f"❌ Не удалось извлечь содержимое из PDF: {file_path}")

    return content


def create_document_hash(file_path: str) -> str:
    """
    Создание хеша документа для БД.

    ВАЖНО: Хеш предотвращает дублирование документов в БД
    """
    utilities = SystemUtilities()
    return utilities.create_file_hash(file_path)