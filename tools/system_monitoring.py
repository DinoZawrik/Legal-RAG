#!/usr/bin/env python3
"""
System Monitoring & Database Utilities
Объединенные утилиты для мониторинга системы и работы с базой данных.

Включает функциональность из:
- quick_status_check.py
- check_db.py

Использование:
    python -m tools.system_monitoring --mode=status
    python -m tools.system_monitoring --mode=database
    python -m tools.system_monitoring --mode=full
"""

import sys
import asyncio
import argparse
import requests
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Core imports
try:
    from sqlalchemy import select, func, text
    from core.infrastructure_suite import get_settings, Document, ProcessingTask
    from core.data_storage_suite import postgres_manager
    from core.logging_config import configure_logging
except ImportError:
    print(" Не удается импортировать core модули")
    sys.exit(1)

# Logging setup
configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


class SystemMonitoringSuite:
    """Объединенные утилиты для мониторинга системы."""

    def __init__(self):
        """Инициализация мониторинга."""
        self.config = get_settings()

    def print_header(self, title: str):
        """Печать заголовка."""
        print("\n" + "="*60)
        print(f" {title}")
        print("="*60)

    # === ПРОВЕРКА СТАТУСА СИСТЕМЫ ===

    def check_database_legacy(self) -> Dict[str, Any]:
        """Проверка базы данных (legacy SQLite - DEPRECATED)."""
        logger.warning(" SQLite проверка устарела - используется PostgreSQL в Docker")

        status = {
            "type": "sqlite_legacy",
            "status": "deprecated",
            "message": "SQLite больше не используется в продакшн",
            "recommendation": "Используйте PostgreSQL через Docker"
        }

        # Проверяем, есть ли еще файлы SQLite
        sqlite_files = list(Path(".").glob("*.db"))
        if sqlite_files:
            status["found_sqlite_files"] = [str(f) for f in sqlite_files]
            status["recommendation"] += ". Удалите устаревшие .db файлы"

        return status

    def check_chromadb_http_status(self) -> Dict[str, Any]:
        """Проверка статуса ChromaDB через HTTP API."""
        chromadb_status = {
            "service": "ChromaDB",
            "status": "unknown",
            "details": {},
            "recommendations": []
        }

        try:
            # Пытаемся подключиться к ChromaDB HTTP API
            chroma_url = self.config.CHROMA_HOST
            logger.info(f" Проверяем ChromaDB: {chroma_url}")

            # Проверка health endpoint
            health_response = requests.get(f"http://{chroma_url}:{self.config.CHROMA_PORT}/api/v1/heartbeat", timeout=5)

            if health_response.status_code == 200:
                chromadb_status["status"] = "running"
                chromadb_status["details"]["heartbeat"] = "OK"

                # Дополнительная информация
                try:
                    version_response = requests.get(f"http://{chroma_url}:{self.config.CHROMA_PORT}/api/v1/version", timeout=5)
                    if version_response.status_code == 200:
                        chromadb_status["details"]["version"] = version_response.text
                except Exception:
                    pass

            else:
                chromadb_status["status"] = "error"
                chromadb_status["details"]["error"] = f"HTTP {health_response.status_code}"

        except requests.ConnectionError:
            chromadb_status["status"] = "unavailable"
            chromadb_status["details"]["error"] = "Не удается подключиться"
            chromadb_status["recommendations"].append(
                "Запустите ChromaDB: docker-compose up chromadb"
            )

        except requests.Timeout:
            chromadb_status["status"] = "timeout"
            chromadb_status["details"]["error"] = "Тайм-аут подключения"
            chromadb_status["recommendations"].append(
                "Проверьте производительность ChromaDB"
            )

        except Exception as e:
            chromadb_status["status"] = "error"
            chromadb_status["details"]["error"] = str(e)

        return chromadb_status

    def check_files(self) -> Dict[str, Any]:
        """Проверка файловой системы."""
        file_status = {
            "file_system": "OK",
            "directories": {},
            "important_files": {},
            "issues": []
        }

        # Проверяем важные директории
        important_dirs = [
            "core", "bot", "tools", "scripts",
            "uploads", "data", "logs"
        ]

        for dir_name in important_dirs:
            dir_path = Path(dir_name)
            file_status["directories"][dir_name] = {
                "exists": dir_path.exists(),
                "is_directory": dir_path.is_dir() if dir_path.exists() else False,
                "files_count": len(list(dir_path.iterdir())) if dir_path.exists() and dir_path.is_dir() else 0
            }

            if not dir_path.exists():
                file_status["issues"].append(f"Отсутствует директория: {dir_name}")

        # Проверяем важные файлы
        important_files = [
            "requirements.txt", "docker-compose.yml",
            ".env", "README.md"
        ]

        for file_name in important_files:
            file_path = Path(file_name)
            file_status["important_files"][file_name] = {
                "exists": file_path.exists(),
                "size": file_path.stat().st_size if file_path.exists() else 0,
                "modified": str(datetime.fromtimestamp(file_path.stat().st_mtime)) if file_path.exists() else None
            }

            if not file_path.exists() and file_name != ".env": # .env опционален
                file_status["issues"].append(f"Отсутствует файл: {file_name}")

        return file_status

    def check_logs(self) -> Dict[str, Any]:
        """Проверка логов."""
        log_status = {
            "log_system": "OK",
            "log_files": {},
            "recent_errors": [],
            "recommendations": []
        }

        # Проверяем директории с логами
        log_dirs = ["logs", ".", "data"]
        log_patterns = ["*.log", "*.out", "*.err"]

        found_logs = []
        for log_dir in log_dirs:
            log_path = Path(log_dir)
            if log_path.exists():
                for pattern in log_patterns:
                    found_logs.extend(log_path.glob(pattern))

        for log_file in found_logs:
            try:
                stat = log_file.stat()
                log_status["log_files"][str(log_file)] = {
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "readable": True
                }

                # Проверяем последние строки на ошибки
                if stat.st_size > 0 and stat.st_size < 1024 * 1024: # Только небольшие файлы
                    try:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            recent_lines = lines[-20:] if len(lines) > 20 else lines

                            for line in recent_lines:
                                if any(error_word in line.lower()
                                      for error_word in ['error', 'exception', 'failed', 'critical']):
                                    log_status["recent_errors"].append({
                                        "file": str(log_file),
                                        "line": line.strip()[:200]
                                    })
                    except Exception:
                        pass

            except Exception as e:
                log_status["log_files"][str(log_file)] = {
                    "error": str(e),
                    "readable": False
                }

        if not found_logs:
            log_status["recommendations"].append("Логи не найдены - проверьте настройку логирования")
        elif len(log_status["recent_errors"]) > 5:
            log_status["recommendations"].append("Обнаружено много ошибок в логах - требуется анализ")

        return log_status

    async def show_processing_status(self) -> Dict[str, Any]:
        """Показать статус обработки документов."""
        processing_status = {
            "document_processing": "unknown",
            "statistics": {},
            "recent_activity": [],
            "recommendations": []
        }

        if not postgres_manager or not postgres_manager.async_session_maker:
            processing_status["document_processing"] = "error"
            processing_status["error"] = "PostgresManager не инициализирован"
            return processing_status

        try:
            async with postgres_manager.async_session_maker() as session:
                # Подсчет документов
                total_docs_result = await session.execute(select(func.count(Document.id)))
                total_docs = total_docs_result.scalar_one()
                processing_status["statistics"]["total_documents"] = total_docs

                # Подсчет задач обработки
                total_tasks_result = await session.execute(select(func.count(ProcessingTask.id)))
                total_tasks = total_tasks_result.scalar_one()
                processing_status["statistics"]["processing_tasks"] = total_tasks

                # Последние документы
                recent_docs_result = await session.execute(
                    select(Document).order_by(Document.created_at.desc()).limit(5)
                )
                recent_docs = recent_docs_result.scalars().all()

                processing_status["recent_activity"] = [
                    {
                        "id": doc.id,
                        "filename": doc.file_name,
                        "created_at": str(doc.created_at),
                        "status": doc.processing_status.value if hasattr(doc.processing_status, 'value') else doc.processing_status
                    }
                    for doc in recent_docs
                ]

                processing_status["document_processing"] = "connected"

                # Рекомендации
                if total_docs == 0:
                    processing_status["recommendations"].append(
                        "Документы не загружены - используйте скрипты загрузки"
                    )
                else:
                    processing_status["recommendations"].append(
                        "Статус обработки документов в норме"
                    )

        except Exception as e:
            processing_status["document_processing"] = "error"
            processing_status["error"] = str(e)
            processing_status["recommendations"].append(
                f"Ошибка подключения к БД: {e}"
            )

        return processing_status

    # === ПРОВЕРКА БАЗЫ ДАННЫХ ===

    async def check_database_connection(self) -> Dict[str, Any]:
        """Проверка подключения к базе данных."""
        db_status = {
            "database": "PostgreSQL",
            "connection": "unknown",
            "statistics": {},
            "health": "unknown",
            "recommendations": []
        }

        if not postgres_manager or not postgres_manager.async_session_maker:
            db_status["connection"] = "failed"
            db_status["error"] = "PostgresManager не инициализирован"
            return db_status

        try:
            async with postgres_manager.async_session_maker() as session:
                # Тест подключения
                result = await session.execute(text("SELECT 1 as test"))
                if result.scalar_one() == 1:
                    db_status["connection"] = "OK"
                    db_status["health"] = "healthy"

                    # Получаем статистику
                    try:
                        # Подсчет таблиц
                        table_count_result = await session.execute(
                            text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
                        )
                        db_status["statistics"]["tables_count"] = table_count_result.scalar_one()

                        # Подсчет документов
                        doc_count_result = await session.execute(select(func.count(Document.id)))
                        doc_count = doc_count_result.scalar_one()
                        db_status["statistics"]["documents_count"] = doc_count

                        # Подсчет задач обработки
                        task_count_result = await session.execute(select(func.count(ProcessingTask.id)))
                        task_count = task_count_result.scalar_one()
                        db_status["statistics"]["processing_tasks_count"] = task_count

                        # Размер базы данных (если доступно)
                        try:
                            db_size_result = await session.execute(
                                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
                            )
                            db_status["statistics"]["database_size"] = db_size_result.scalar_one()
                        except Exception:
                            db_status["statistics"]["database_size"] = "Недоступно"

                    except Exception as e:
                        db_status["statistics"]["error"] = str(e)

                    # Рекомендации
                    if doc_count == 0:
                        db_status["recommendations"].append(
                            "База данных пуста - загрузите документы"
                        )
                    else:
                        db_status["recommendations"].append(
                            "База данных функционирует нормально"
                        )

        except Exception as e:
            db_status["connection"] = "failed"
            db_status["health"] = "unhealthy"
            db_status["error"] = str(e)
            db_status["recommendations"].append(
                f"Ошибка подключения: {e}. Проверьте Docker контейнеры"
            )

        return db_status

    async def analyze_database_performance(self) -> Dict[str, Any]:
        """Анализ производительности базы данных."""
        performance_analysis = {
            "performance": "unknown",
            "query_tests": {},
            "timing": {},
            "recommendations": []
        }

        if not postgres_manager or not postgres_manager.async_session_maker:
            performance_analysis["performance"] = "error"
            performance_analysis["error"] = "PostgresManager не инициализирован"
            return performance_analysis

        try:
            async with postgres_manager.async_session_maker() as session:
                import time

                # Тест простого запроса
                start_time = time.time()
                await session.execute(text("SELECT 1"))
                simple_query_time = time.time() - start_time

                performance_analysis["timing"]["simple_query"] = simple_query_time
                performance_analysis["query_tests"]["simple_query"] = "OK"

                # Тест запроса к документам
                start_time = time.time()
                doc_count_result = await session.execute(select(func.count(Document.id)))
                doc_count = doc_count_result.scalar_one()
                count_query_time = time.time() - start_time

                performance_analysis["timing"]["count_query"] = count_query_time
                performance_analysis["query_tests"]["count_query"] = "OK"
                performance_analysis["statistics"] = {"document_count": doc_count}

                # Тест сложного запроса (если есть данные)
                if doc_count > 0:
                    start_time = time.time()
                    await session.execute(
                        select(Document).order_by(Document.created_at.desc()).limit(10)
                    )
                    complex_query_time = time.time() - start_time

                    performance_analysis["timing"]["complex_query"] = complex_query_time
                    performance_analysis["query_tests"]["complex_query"] = "OK"

                # Анализ производительности
                if performance_analysis["timing"]:
                    avg_time = sum(performance_analysis["timing"].values()) / len(performance_analysis["timing"])

                    if avg_time < 0.1:
                        performance_analysis["performance"] = "excellent"
                    elif avg_time < 0.5:
                        performance_analysis["performance"] = "good"
                    elif avg_time < 2.0:
                        performance_analysis["performance"] = "acceptable"
                    else:
                        performance_analysis["performance"] = "poor"
                        performance_analysis["recommendations"].append(
                            "Производительность БД низкая - проверьте ресурсы"
                        )

        except Exception as e:
            performance_analysis["performance"] = "error"
            performance_analysis["error"] = str(e)
            performance_analysis["recommendations"].append(
                f"Ошибка тестирования производительности: {e}"
            )

        return performance_analysis

    # === ОСНОВНЫЕ МЕТОДЫ ===

    async def run_status_check(self) -> Dict[str, Any]:
        """Запускает проверку статуса системы."""
        logger.info(" Запуск проверки статуса системы...")

        status_report = {
            "timestamp": datetime.now().isoformat(),
            "chromadb": self.check_chromadb_http_status(),
            "files": self.check_files(),
            "logs": self.check_logs(),
            "processing": await self.show_processing_status(),
            "database_legacy": self.check_database_legacy()
        }

        return status_report

    async def run_database_check(self) -> Dict[str, Any]:
        """Запускает проверку базы данных."""
        logger.info(" Запуск проверки базы данных...")

        database_report = {
            "timestamp": datetime.now().isoformat(),
            "connection": await self.check_database_connection(),
            "performance": await self.analyze_database_performance()
        }

        return database_report

    async def run_full_monitoring(self) -> Dict[str, Any]:
        """Запускает полный мониторинг системы."""
        logger.info(" Запуск полного мониторинга системы...")

        full_report = {
            "timestamp": datetime.now().isoformat(),
            "system_status": await self.run_status_check(),
            "database_status": await self.run_database_check()
        }

        return full_report

    def generate_monitoring_report(self, results: Dict[str, Any],
                                 output_file: str = "system_monitoring_report.json"):
        """Генерирует отчет по мониторингу."""
        logger.info(f" Сохраняем отчет в {output_file}")

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # Краткий отчет в консоль
        self.print_header("ОТЧЕТ ПО МОНИТОРИНГУ СИСТЕМЫ")

        # Статус ChromaDB
        if "system_status" in results and "chromadb" in results["system_status"]:
            chromadb = results["system_status"]["chromadb"]
            status_icon = "" if chromadb["status"] == "running" else ""
            print(f"{status_icon} ChromaDB: {chromadb['status']}")

        # Статус базы данных
        if "database_status" in results and "connection" in results["database_status"]:
            db_conn = results["database_status"]["connection"]
            status_icon = "" if db_conn["connection"] == "OK" else ""
            print(f"{status_icon} База данных: {db_conn['connection']}")

            if "statistics" in db_conn:
                stats = db_conn["statistics"]
                print(f" Документов: {stats.get('documents_count', 0)}")
                print(f" Задач обработки: {stats.get('processing_tasks_count', 0)}")

        # Статус файловой системы
        if "system_status" in results and "files" in results["system_status"]:
            files = results["system_status"]["files"]
            issues_count = len(files.get("issues", []))
            status_icon = "" if issues_count == 0 else ""
            print(f"{status_icon} Файловая система: {issues_count} проблем")

        # Производительность
        if "database_status" in results and "performance" in results["database_status"]:
            perf = results["database_status"]["performance"]
            performance = perf.get("performance", "unknown")
            print(f" Производительность БД: {performance}")

        print(f"\n Полный отчет сохранен в: {output_file}")
        print("="*60)


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="System Monitoring & Database Utilities")
    parser.add_argument(
        "--mode",
        choices=["status", "database", "full"],
        default="full",
        help="Режим мониторинга"
    )
    parser.add_argument(
        "--output",
        default="system_monitoring_report.json",
        help="Файл для отчета"
    )

    args = parser.parse_args()

    suite = SystemMonitoringSuite()

    try:
        # Инициализация менеджера БД
        if not await postgres_manager.initialize():
            logger.error("Не удалось инициализировать PostgreSQL. Выход.")
            return

        if args.mode == "status":
            results = await suite.run_status_check()
        elif args.mode == "database":
            results = await suite.run_database_check()
        else: # full
            results = await suite.run_full_monitoring()

        suite.generate_monitoring_report(results, args.output)

    except Exception as e:
        logger.error(f" Ошибка мониторинга: {e}")
        print(f" Ошибка: {e}")
    finally:
        if postgres_manager:
            await postgres_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
