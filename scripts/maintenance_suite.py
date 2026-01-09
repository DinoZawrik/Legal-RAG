#!/usr/bin/env python3
"""
🔧 Maintenance Suite
Объединенный инструмент для обслуживания и управления системой.

Включает функциональность из папки maintenance/:
- clear_all_databases.py
- clear_chromadb.py
- final_cleanup.py
- fix_database_records.py
- fix_database_schema.py
- reindex_documents.py
- update_documents_table.py
- update_table_simple.py

Использование:
    python -m scripts.maintenance_suite --mode=clear-all
    python -m scripts.maintenance_suite --mode=clear-chroma
    python -m scripts.maintenance_suite --mode=fix-schema
    python -m scripts.maintenance_suite --mode=reindex
    python -m scripts.maintenance_suite --mode=cleanup
    python -m scripts.maintenance_suite --mode=full
"""

import sys
import asyncio
import argparse
import logging
import os
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Core imports
try:
    from core.infrastructure_suite import get_settings
    from core.data_storage_suite import get_session, Document, engine
    from core.processing_pipeline import DocumentManager
    from core.logging_config import configure_logging
except ImportError as e:
    print(f"❌ Не удается импортировать core модули: {e}")
    sys.exit(1)

# Database imports
try:
    from sqlalchemy import text, inspect
except ImportError as e:
    print(f"⚠️ SQLAlchemy недоступен: {e}")

logger = logging.getLogger(__name__)


class MaintenanceSuite:
    """Объединенный инструмент для обслуживания системы."""
    
    def __init__(self):
        """Инициализация suite."""
        self.config = get_settings()
        self.operations = []
        self.start_time = datetime.now()
        
    def log_operation(self, operation: str, status: str, details: str, duration: float = None):
        """Логирование операции обслуживания."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "status": status,
            "details": details,
            "duration_ms": round(duration * 1000, 2) if duration else None
        }
        self.operations.append(result)
        
        emoji = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
        duration_str = f" ({duration*1000:.1f}ms)" if duration else ""
        logger.info(f"{emoji} {operation}: {details}{duration_str}")
    
    # === DATABASE CLEARING ===
    
    async def clear_all_databases(self, confirm: bool = False) -> Dict[str, Any]:
        """Полная очистка всех баз данных."""
        logger.info("🗑️ Запуск полной очистки баз данных")
        
        if not confirm:
            logger.warning("⚠️ Операция требует подтверждения. Используйте --confirm")
            return {"error": "Требуется подтверждение", "cleared": False}
        
        results = {
            "cleared_tables": [],
            "errors": [],
            "total_records_deleted": 0
        }
        
        try:
            with get_session() as session:
                # Получение списка таблиц
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                
                # Очистка таблиц в правильном порядке (учитывая внешние ключи)
                tables_to_clear = [
                    "processing_results",
                    "documents", 
                    "user_sessions",
                    "user_interactions"
                ]
                
                for table_name in tables_to_clear:
                    if table_name in tables:
                        try:
                            start_time = time.time()
                            
                            # Подсчет записей перед удалением
                            count_result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                            
                            # Удаление записей
                            session.execute(text(f"DELETE FROM {table_name}"))
                            session.commit()
                            
                            operation_time = time.time() - start_time
                            
                            results["cleared_tables"].append(table_name)
                            results["total_records_deleted"] += count_result
                            
                            self.log_operation(
                                "clear_table", 
                                "success", 
                                f"Таблица {table_name}: удалено {count_result} записей",
                                operation_time
                            )
                            
                        except Exception as e:
                            error_msg = f"Ошибка очистки {table_name}: {e}"
                            results["errors"].append(error_msg)
                            self.log_operation("clear_table", "error", error_msg)
            
            # Сброс автоинкрементов
            try:
                with get_session() as session:
                    for table_name in results["cleared_tables"]:
                        session.execute(text(f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH 1"))
                    session.commit()
                
                self.log_operation("reset_sequences", "success", "Сброшены автоинкременты")
                
            except Exception as e:
                results["errors"].append(f"Ошибка сброса автоинкрементов: {e}")
            
            results["success"] = len(results["errors"]) == 0
            
            return results
            
        except Exception as e:
            self.log_operation("clear_all_databases", "error", f"Критическая ошибка: {e}")
            return {"error": str(e), "cleared": False}
    
    async def clear_chroma_database(self) -> Dict[str, Any]:
        """Очистка ChromaDB."""
        logger.info("🔍 Очистка ChromaDB")
        
        try:
            # Пробуем подключиться к ChromaDB
            import chromadb
            
            # Получение клиента ChromaDB
            chroma_client = chromadb.Client()
            
            # Получение списка коллекций
            collections = chroma_client.list_collections()
            
            results = {
                "collections_deleted": [],
                "errors": [],
                "total_collections": len(collections)
            }
            
            for collection in collections:
                try:
                    start_time = time.time()
                    
                    # Получение количества документов
                    doc_count = collection.count()
                    
                    # Удаление коллекции
                    chroma_client.delete_collection(collection.name)
                    
                    operation_time = time.time() - start_time
                    
                    results["collections_deleted"].append({
                        "name": collection.name,
                        "documents_count": doc_count
                    })
                    
                    self.log_operation(
                        "clear_chroma_collection",
                        "success",
                        f"Коллекция {collection.name}: удалено {doc_count} документов",
                        operation_time
                    )
                    
                except Exception as e:
                    error_msg = f"Ошибка удаления коллекции {collection.name}: {e}"
                    results["errors"].append(error_msg)
                    self.log_operation("clear_chroma_collection", "error", error_msg)
            
            results["success"] = len(results["errors"]) == 0
            
            return results
            
        except ImportError:
            self.log_operation("clear_chroma", "error", "ChromaDB не установлен")
            return {"error": "ChromaDB не доступен"}
        except Exception as e:
            self.log_operation("clear_chroma", "error", f"Ошибка очистки ChromaDB: {e}")
            return {"error": str(e)}
    
    # === DATABASE FIXES ===
    
    async def fix_database_schema(self) -> Dict[str, Any]:
        """Исправление схемы базы данных."""
        logger.info("🔧 Исправление схемы базы данных")
        
        results = {
            "fixes_applied": [],
            "errors": [],
            "migrations_run": []
        }
        
        try:
            with get_session() as session:
                # Проверка существования таблиц
                inspector = inspect(engine)
                existing_tables = inspector.get_table_names()
                
                required_tables = ["documents", "processing_results", "user_sessions"]
                
                for table in required_tables:
                    if table not in existing_tables:
                        self.log_operation("check_table", "error", f"Отсутствует таблица: {table}")
                        results["errors"].append(f"Отсутствует таблица: {table}")
                
                # Проверка колонок в таблице documents
                if "documents" in existing_tables:
                    columns = inspector.get_columns("documents")
                    column_names = [col["name"] for col in columns]
                    
                    required_columns = ["id", "title", "content", "source_path", "metadata", "created_at"]
                    
                    for col in required_columns:
                        if col not in column_names:
                            try:
                                # Попытка добавить недостающую колонку
                                if col == "metadata":
                                    session.execute(text("ALTER TABLE documents ADD COLUMN metadata JSONB"))
                                elif col == "created_at":
                                    session.execute(text("ALTER TABLE documents ADD COLUMN created_at TIMESTAMP DEFAULT NOW()"))
                                
                                session.commit()
                                results["fixes_applied"].append(f"Добавлена колонка {col}")
                                self.log_operation("fix_column", "success", f"Добавлена колонка {col}")
                                
                            except Exception as e:
                                error_msg = f"Ошибка добавления колонки {col}: {e}"
                                results["errors"].append(error_msg)
                                self.log_operation("fix_column", "error", error_msg)
                
                # Проверка индексов
                try:
                    # Создание индекса на метаданные (если его нет)
                    session.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING gin(metadata)"
                    ))
                    
                    # Создание индекса на дату создания
                    session.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at)"
                    ))
                    
                    session.commit()
                    results["fixes_applied"].append("Проверены/созданы индексы")
                    self.log_operation("fix_indexes", "success", "Индексы проверены/созданы")
                    
                except Exception as e:
                    error_msg = f"Ошибка создания индексов: {e}"
                    results["errors"].append(error_msg)
                    self.log_operation("fix_indexes", "error", error_msg)
            
            results["success"] = len(results["errors"]) == 0
            
            return results
            
        except Exception as e:
            self.log_operation("fix_database_schema", "error", f"Критическая ошибка: {e}")
            return {"error": str(e)}
    
    async def fix_database_records(self) -> Dict[str, Any]:
        """Исправление записей в базе данных."""
        logger.info("📝 Исправление записей в БД")
        
        results = {
            "fixes_applied": [],
            "records_updated": 0,
            "errors": []
        }
        
        try:
            with get_session() as session:
                # Поиск документов с пустыми заголовками
                docs_without_title = session.query(Document).filter(
                    (Document.title == '') | (Document.title.is_(None))
                ).all()
                
                for doc in docs_without_title:
                    try:
                        # Генерация заголовка на основе содержимого
                        if doc.content:
                            # Берем первые 50 символов содержимого
                            title = doc.content[:50].strip()
                            if len(title) < 10:
                                title = f"Документ #{doc.id}"
                        else:
                            title = f"Документ #{doc.id}"
                        
                        doc.title = title
                        results["records_updated"] += 1
                        
                    except Exception as e:
                        results["errors"].append(f"Ошибка обновления документа {doc.id}: {e}")
                
                # Поиск документов с некорректными метаданными
                docs_with_bad_metadata = session.query(Document).filter(
                    Document.metadata.is_(None)
                ).all()
                
                for doc in docs_with_bad_metadata:
                    try:
                        doc.metadata = {"fixed": True, "fixed_at": datetime.now().isoformat()}
                        results["records_updated"] += 1
                        
                    except Exception as e:
                        results["errors"].append(f"Ошибка обновления метаданных {doc.id}: {e}")
                
                session.commit()
                
                if results["records_updated"] > 0:
                    results["fixes_applied"].append(f"Обновлено {results['records_updated']} записей")
                    self.log_operation(
                        "fix_records", 
                        "success", 
                        f"Исправлено {results['records_updated']} записей"
                    )
                else:
                    self.log_operation("fix_records", "success", "Некорректных записей не найдено")
            
            results["success"] = len(results["errors"]) == 0
            
            return results
            
        except Exception as e:
            self.log_operation("fix_database_records", "error", f"Ошибка исправления записей: {e}")
            return {"error": str(e)}
    
    # === REINDEXING ===
    
    async def reindex_documents(self) -> Dict[str, Any]:
        """Переиндексация документов."""
        logger.info("🔄 Переиндексация документов")
        
        results = {
            "documents_processed": 0,
            "documents_reindexed": 0,
            "errors": []
        }
        
        try:
            # Получение всех документов
            with get_session() as session:
                documents = session.query(Document).all()
                results["documents_processed"] = len(documents)
            
            if not documents:
                self.log_operation("reindex", "warning", "Нет документов для переиндексации")
                return results
            
            # Инициализация менеджера документов
            doc_manager = DocumentManager()
            
            for i, doc in enumerate(documents, 1):
                try:
                    # Переиндексация через DocumentManager
                    await doc_manager.reindex_document(doc.id)
                    
                    results["documents_reindexed"] += 1
                    
                    if i % 10 == 0:
                        logger.info(f"Переиндексировано {i}/{len(documents)} документов")
                    
                    # Небольшая пауза между операциями
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    error_msg = f"Ошибка переиндексации документа {doc.id}: {e}"
                    results["errors"].append(error_msg)
                    self.log_operation("reindex_document", "error", error_msg)
            
            self.log_operation(
                "reindex_documents",
                "success",
                f"Переиндексировано {results['documents_reindexed']}/{results['documents_processed']} документов"
            )
            
            results["success"] = len(results["errors"]) == 0
            
            return results
            
        except Exception as e:
            self.log_operation("reindex_documents", "error", f"Критическая ошибка переиндексации: {e}")
            return {"error": str(e)}
    
    # === CLEANUP ===
    
    async def final_cleanup(self) -> Dict[str, Any]:
        """Финальная очистка системы."""
        logger.info("🧹 Финальная очистка системы")
        
        results = {
            "cleanup_operations": [],
            "space_freed_mb": 0,
            "errors": []
        }
        
        try:
            # Очистка временных файлов
            import tempfile
            
            temp_dir = tempfile.gettempdir()
            temp_files_size = 0
            
            # Удаление старых временных файлов (старше 1 дня)
            for file_path in Path(temp_dir).glob("*.tmp"):
                try:
                    if file_path.stat().st_mtime < (datetime.now().timestamp() - 86400):
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        temp_files_size += file_size
                        
                except Exception:
                    pass  # Игнорируем ошибки доступа к временным файлам
            
            if temp_files_size > 0:
                results["cleanup_operations"].append("Удалены временные файлы")
                results["space_freed_mb"] += temp_files_size / 1024 / 1024
            
            # Очистка логов (если есть)
            log_files = Path("logs/").glob("*.log") if Path("logs/").exists() else []
            for log_file in log_files:
                try:
                    if log_file.stat().st_size > 100 * 1024 * 1024:  # 100MB
                        # Сжатие больших логов
                        with open(log_file, 'r') as f:
                            lines = f.readlines()
                        
                        # Оставляем только последние 1000 строк
                        with open(log_file, 'w') as f:
                            f.writelines(lines[-1000:])
                        
                        results["cleanup_operations"].append(f"Сжат лог {log_file.name}")
                        
                except Exception as e:
                    results["errors"].append(f"Ошибка очистки лога {log_file}: {e}")
            
            # Очистка кэша Python
            import gc
            gc.collect()
            
            results["cleanup_operations"].append("Выполнена сборка мусора")
            
            # Вакуумирование базы данных
            try:
                with get_session() as session:
                    session.execute(text("VACUUM ANALYZE"))
                    session.commit()
                
                results["cleanup_operations"].append("Выполнено вакуумирование БД")
                
            except Exception as e:
                results["errors"].append(f"Ошибка вакуумирования: {e}")
            
            self.log_operation(
                "final_cleanup",
                "success",
                f"Очистка завершена: {len(results['cleanup_operations'])} операций"
            )
            
            results["success"] = len(results["errors"]) == 0
            
            return results
            
        except Exception as e:
            self.log_operation("final_cleanup", "error", f"Ошибка финальной очистки: {e}")
            return {"error": str(e)}
    
    # === MAIN METHODS ===
    
    async def run_full_maintenance(self, confirm_clear: bool = False) -> Dict[str, Any]:
        """Запуск полного обслуживания системы."""
        logger.info("🔧 Запуск полного обслуживания системы")
        
        results = {
            "maintenance_type": "full",
            "timestamp": datetime.now().isoformat(),
            "operations": {}
        }
        
        # 1. Исправление схемы
        schema_results = await self.fix_database_schema()
        results["operations"]["schema_fix"] = schema_results
        
        # 2. Исправление записей
        records_results = await self.fix_database_records()
        results["operations"]["records_fix"] = records_results
        
        # 3. Переиндексация (если схема и записи в порядке)
        if schema_results.get("success") and records_results.get("success"):
            reindex_results = await self.reindex_documents()
            results["operations"]["reindex"] = reindex_results
        
        # 4. Очистка ChromaDB (если запрошено)
        if confirm_clear:
            chroma_results = await self.clear_chroma_database()
            results["operations"]["chroma_clear"] = chroma_results
        
        # 5. Финальная очистка
        cleanup_results = await self.final_cleanup()
        results["operations"]["cleanup"] = cleanup_results
        
        # Подсчет общего результата
        all_operations = [op for op in results["operations"].values() if "success" in op]
        successful_operations = [op for op in all_operations if op.get("success")]
        
        results["summary"] = {
            "total_operations": len(all_operations),
            "successful_operations": len(successful_operations),
            "success_rate": (len(successful_operations) / max(1, len(all_operations))) * 100
        }
        
        return results
    
    def generate_report(self, results: Dict[str, Any], output_file: str = "maintenance_report.json"):
        """Генерация отчета обслуживания."""
        # Добавление информации о сессии
        results["session_info"] = {
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "total_operations": len(self.operations),
            "successful_operations": len([op for op in self.operations if op["status"] == "success"]),
            "failed_operations": len([op for op in self.operations if op["status"] == "error"])
        }
        
        # Сохранение в файл
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        # Краткий отчет
        print("\n" + "="*60)
        print("🔧 ОТЧЕТ ПО ОБСЛУЖИВАНИЮ СИСТЕМЫ")
        print("="*60)
        
        maintenance_type = results.get("maintenance_type", "unknown")
        print(f"🛠️ Тип обслуживания: {maintenance_type}")
        print(f"⏱️ Продолжительность: {results['session_info']['duration_seconds']:.1f}с")
        print(f"✅ Успешных операций: {results['session_info']['successful_operations']}")
        print(f"❌ Неудачных операций: {results['session_info']['failed_operations']}")
        
        if "summary" in results:
            print(f"📊 Общая успешность: {results['summary']['success_rate']:.1f}%")
        
        print(f"\n💾 Полный отчет сохранен в: {output_file}")
        print("="*60)


async def main_async(args: argparse.Namespace) -> Dict[str, Any]:
    suite = MaintenanceSuite()
    start_time = time.time()
    
    try:
        if args.mode == "clear-all":
            results = await suite.clear_all_databases(args.confirm)
        elif args.mode == "clear-chroma":
            results = await suite.clear_chroma_database()
        elif args.mode == "fix-schema":
            results = await suite.fix_database_schema()
        elif args.mode == "fix-records":
            results = await suite.fix_database_records()
        elif args.mode == "reindex":
            results = await suite.reindex_documents()
        elif args.mode == "cleanup":
            results = await suite.final_cleanup()
        else:  # full
            results = await suite.run_full_maintenance(args.confirm)
        
        suite.generate_report(results, args.output)
        
        # Определение кода завершения
        if isinstance(results, dict):
            if "success" in results:
                sys.exit(0 if results["success"] else 1)
            elif "summary" in results:
                success_rate = results["summary"].get("success_rate", 0)
                sys.exit(0 if success_rate > 80 else 1)
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка обслуживания: {e}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintenance tool for LegalRAG")
    parser.add_argument("--mode", choices=[
        "clear-all", "clear-chroma", "fix-schema", "fix-records",
        "reindex", "cleanup", "full"
    ], default="full",
        help="Режим обслуживания")
    parser.add_argument("--confirm", action="store_true", help="Подтверждение опасных операций")
    args = parser.parse_args()

    configure_logging(os.getenv("LOG_LEVEL", "INFO"))

    results = asyncio.run(main_async(args))

    # Вывод результата в JSON
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # Определение кода завершения
    if isinstance(results, dict):
        if "success" in results:
            sys.exit(0 if results["success"] else 1)
        elif "summary" in results:
            success_rate = results["summary"].get("success_rate", 0)
            sys.exit(0 if success_rate > 80 else 1)

    sys.exit(0)


if __name__ == "__main__":
    main()
