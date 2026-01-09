#!/usr/bin/env python3
"""
📄 Document Loading Suite
Объединенный инструмент для загрузки и управления документами.

Включает функциональность из:
- load_pdf_documents.py
- load_test_documents.py  
- test_runner.py

Использование:
    python -m scripts.document_suite --mode=pdf --path="/path/to/pdfs"
    python -m scripts.document_suite --mode=test --count=5
    python -m scripts.document_suite --mode=run-tests
    python -m scripts.document_suite --mode=full --path="/path" --count=10
"""

import sys
import asyncio
import argparse
import logging
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import json

# Core imports
try:
    from core.infrastructure_suite import get_settings
    from core.data_storage_suite import get_session, Document
    from core.processing_pipeline import DocumentManager
    from core.ai_inference_suite import UnifiedAISystem
    from core.processing_pipeline import IngestionPipeline
    from core.logging_config import configure_logging
except ImportError as e:
    print(f"❌ Не удается импортировать core модули: {e}")
    sys.exit(1)

# Additional imports
try:
    import PyPDF2
except ImportError as e:
    print(f"⚠️ PyPDF2 недоступен: {e}")

# Logging setup
configure_logging()
logger = logging.getLogger(__name__)


class DocumentSuite:
    """Объединенный инструмент для загрузки и тестирования документов."""
    
    def __init__(self):
        """Инициализация suite."""
        self.config = get_settings()
        self.stats = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None,
            "end_time": None
        }
        self.results = []
        
    def log_result(self, operation: str, status: str, message: str, file_path: str = None):
        """Логирование результата операции."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "status": status,
            "message": message,
            "file_path": file_path
        }
        self.results.append(result)
        
        emoji = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
        logger.info(f"{emoji} {operation}: {message}")
        
        if status == "success":
            self.stats["successful"] += 1
        elif status == "error":
            self.stats["failed"] += 1
        else:
            self.stats["skipped"] += 1
        
        self.stats["processed"] += 1
    
    # === PDF LOADING ===
    
    def find_pdf_files(self, directory: str) -> List[Path]:
        """Поиск PDF файлов в директории."""
        pdf_files = []
        search_path = Path(directory)
        
        if not search_path.exists():
            self.log_result("find_pdfs", "error", f"Директория не существует: {directory}")
            return pdf_files
        
        # Рекурсивный поиск PDF файлов
        for pdf_file in search_path.rglob("*.pdf"):
            if pdf_file.is_file():
                pdf_files.append(pdf_file)
        
        self.log_result("find_pdfs", "success", f"Найдено PDF файлов: {len(pdf_files)}", str(search_path))
        return pdf_files
    
    def validate_pdf_file(self, file_path: Path) -> bool:
        """Валидация PDF файла."""
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                page_count = len(reader.pages)
                
                if page_count == 0:
                    self.log_result("validate_pdf", "error", "PDF файл пустой", str(file_path))
                    return False
                
                # Проверка первой страницы на читаемость
                first_page = reader.pages[0]
                text = first_page.extract_text()
                
                if len(text.strip()) < 10:
                    self.log_result("validate_pdf", "error", "PDF содержит мало текста", str(file_path))
                    return False
                
                self.log_result("validate_pdf", "success", f"PDF валиден ({page_count} стр.)", str(file_path))
                return True
                
        except Exception as e:
            self.log_result("validate_pdf", "error", f"Ошибка валидации: {e}", str(file_path))
            return False
    
    async def load_pdf_document(self, file_path: Path) -> bool:
        """Загрузка одного PDF документа."""
        try:
            # Проверка, что файл не загружен ранее
            with get_session() as session:
                existing = session.query(Document).filter(
                    Document.source_path == str(file_path)
                ).first()
                
                if existing:
                    self.log_result("load_pdf", "skipped", "Файл уже загружен", str(file_path))
                    return True
            
            # Инициализация pipeline
            pipeline = IngestionPipeline()
            
            # Загрузка и обработка
            start_time = time.time()
            result = await pipeline.process_document(str(file_path))
            process_time = time.time() - start_time
            
            if result.get("success", False):
                self.log_result(
                    "load_pdf", 
                    "success", 
                    f"Загружен за {process_time:.1f}с", 
                    str(file_path)
                )
                return True
            else:
                error_msg = result.get("error", "Неизвестная ошибка")
                self.log_result("load_pdf", "error", f"Ошибка загрузки: {error_msg}", str(file_path))
                return False
                
        except Exception as e:
            self.log_result("load_pdf", "error", f"Исключение: {e}", str(file_path))
            return False
    
    async def load_pdf_batch(self, directory: str, max_files: int = None) -> Dict[str, Any]:
        """Пакетная загрузка PDF файлов."""
        logger.info(f"🚀 Начинаем пакетную загрузку PDF из: {directory}")
        self.stats["start_time"] = datetime.now()
        
        # Поиск файлов
        pdf_files = self.find_pdf_files(directory)
        if not pdf_files:
            return self._generate_summary("Нет PDF файлов для загрузки")
        
        # Ограничение количества файлов
        if max_files and len(pdf_files) > max_files:
            pdf_files = pdf_files[:max_files]
            logger.info(f"📊 Ограничиваем загрузку до {max_files} файлов")
        
        # Валидация файлов
        valid_files = []
        for pdf_file in pdf_files:
            if self.validate_pdf_file(pdf_file):
                valid_files.append(pdf_file)
        
        logger.info(f"📄 Валидных PDF файлов: {len(valid_files)}")
        
        # Загрузка файлов
        successful_loads = 0
        for i, pdf_file in enumerate(valid_files, 1):
            logger.info(f"📄 Обрабатываем {i}/{len(valid_files)}: {pdf_file.name}")
            
            success = await self.load_pdf_document(pdf_file)
            if success:
                successful_loads += 1
            
            # Небольшая пауза между загрузками
            await asyncio.sleep(0.1)
        
        self.stats["end_time"] = datetime.now()
        
        return self._generate_summary(f"Загружено {successful_loads}/{len(valid_files)} PDF файлов")
    
    # === TEST DOCUMENTS ===
    
    def generate_test_document_content(self, doc_type: str, index: int) -> str:
        """Генерация контента тестового документа."""
        if doc_type == "regulation":
            return f"""
ТЕСТОВОЕ ПОСТАНОВЛЕНИЕ №{index}
О РЕГУЛИРОВАНИИ ТЕСТОВОЙ ДЕЯТЕЛЬНОСТИ

В соответствии с федеральным законом "О тестировании системы"
ПОСТАНОВЛЯЮ:

1. Установить тестовые требования к обработке документов:
   - Минимальная скорость обработки: 100 мс
   - Максимальный размер документа: 10 МБ
   - Поддерживаемые форматы: PDF, DOCX, TXT

2. Определить процедуру тестирования:
   - Автоматическая валидация контента
   - Проверка извлечения метаданных
   - Тестирование поисковых запросов

3. Настоящее постановление вступает в силу немедленно.

Дата: {datetime.now().strftime('%d.%m.%Y')}
Тестовый документ #{index}
"""
        
        elif doc_type == "law":
            return f"""
ФЕДЕРАЛЬНЫЙ ЗАКОН №{index}-ФЗ
О ТЕСТОВОЙ СИСТЕМЕ ОБРАБОТКИ ДОКУМЕНТОВ

Статья 1. Общие положения
Настоящий федеральный закон регулирует тестирование систем обработки документов.

Статья 2. Основные принципы
1) Принцип автоматизации тестирования
2) Принцип валидации результатов
3) Принцип масштабируемости тестов

Статья 3. Требования к системе
Система должна обеспечивать:
- Быструю обработку документов
- Точное извлечение информации
- Надежное хранение данных

Статья 4. Заключительные положения
Настоящий закон вступает в силу с момента публикации.

Дата принятия: {datetime.now().strftime('%d.%m.%Y')}
Тестовый закон #{index}
"""
        
        elif doc_type == "instruction":
            return f"""
ИНСТРУКЦИЯ ПО ТЕСТИРОВАНИЮ №{index}

1. ОБЩИЕ ПОЛОЖЕНИЯ
Настоящая инструкция определяет порядок тестирования системы.

2. ПРОЦЕДУРЫ ТЕСТИРОВАНИЯ
2.1. Подготовка тестовых данных
2.2. Выполнение тестовых сценариев
2.3. Анализ результатов

3. КРИТЕРИИ УСПЕШНОСТИ
- Все тесты проходят без ошибок
- Время обработки в пределах нормы
- Качество извлечения данных соответствует требованиям

4. ОТЧЕТНОСТЬ
По результатам тестирования составляется отчет.

Версия инструкции: 1.{index}
Дата: {datetime.now().strftime('%d.%m.%Y')}
"""
        
        else:  # general
            return f"""
ТЕСТОВЫЙ ДОКУМЕНТ №{index}

Это тестовый документ для проверки работы системы обработки документов.

СОДЕРЖАНИЕ:
- Тестовая информация для проверки извлечения текста
- Структурированные данные для анализа
- Ключевые слова: тест, документ, система, обработка

ПАРАМЕТРЫ ДОКУМЕНТА:
- Номер: {index}
- Тип: Общий тестовый документ
- Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
- Статус: Активный

ЗАКЛЮЧЕНИЕ:
Документ создан для тестирования системы и проверки корректности работы
алгоритмов обработки и индексации документов.
"""
    
    async def create_test_document(self, doc_type: str, index: int) -> bool:
        """Создание одного тестового документа."""
        try:
            # Генерация контента
            content = self.generate_test_document_content(doc_type, index)
            
            # Создание метаданных
            title = f"Тестовый {doc_type} №{index}"
            filename = f"test_{doc_type}_{index}.txt"
            
            # Сохранение в систему через DocumentManager
            doc_manager = DocumentManager()
            result = await doc_manager.add_document(
                title=title,
                content=content,
                source_type="test",
                metadata={
                    "type": doc_type,
                    "index": index,
                    "filename": filename,
                    "created_for_testing": True
                }
            )
            
            if result.get("success"):
                self.log_result("create_test", "success", f"Создан {doc_type} #{index}")
                return True
            else:
                error = result.get("error", "Неизвестная ошибка")
                self.log_result("create_test", "error", f"Ошибка создания: {error}")
                return False
                
        except Exception as e:
            self.log_result("create_test", "error", f"Исключение: {e}")
            return False
    
    async def generate_test_documents(self, count: int = 10) -> Dict[str, Any]:
        """Генерация набора тестовых документов."""
        logger.info(f"🧪 Создаем {count} тестовых документов")
        self.stats["start_time"] = datetime.now()
        
        doc_types = ["regulation", "law", "instruction", "general"]
        successful_creates = 0
        
        for i in range(1, count + 1):
            doc_type = doc_types[(i - 1) % len(doc_types)]
            
            logger.info(f"📄 Создаем документ {i}/{count}: {doc_type}")
            success = await self.create_test_document(doc_type, i)
            
            if success:
                successful_creates += 1
            
            # Небольшая пауза
            await asyncio.sleep(0.1)
        
        self.stats["end_time"] = datetime.now()
        
        return self._generate_summary(f"Создано {successful_creates}/{count} тестовых документов")
    
    # === TESTING RUNNER ===
    
    async def run_qa_tests(self) -> Dict[str, Any]:
        """Запуск тестов QA системы."""
        logger.info("🔍 Запуск тестов QA системы")
        
        test_queries = [
            "тестовый документ",
            "постановление",
            "федеральный закон",
            "инструкция",
            "регулирование",
            "требования к системе",
            "процедура тестирования"
        ]
        
        try:
            qa_service = UnifiedAISystem()
            test_results = []
            
            for i, query in enumerate(test_queries, 1):
                logger.info(f"🔍 Тест {i}/{len(test_queries)}: '{query}'")
                
                start_time = time.time()
                results = await qa_service.search_documents(query, limit=5)
                search_time = time.time() - start_time
                
                test_result = {
                    "query": query,
                    "results_count": len(results) if results else 0,
                    "search_time_ms": round(search_time * 1000, 1),
                    "success": bool(results)
                }
                test_results.append(test_result)
                
                status = "success" if results else "error"
                self.log_result("qa_test", status, f"Запрос '{query}': {len(results or [])} результатов за {search_time*1000:.1f}мс")
            
            # Статистика тестов
            successful_tests = sum(1 for t in test_results if t["success"])
            avg_time = sum(t["search_time_ms"] for t in test_results) / len(test_results)
            
            summary = f"QA тесты: {successful_tests}/{len(test_queries)} успешных, среднее время {avg_time:.1f}мс"
            
            return {
                "summary": summary,
                "test_results": test_results,
                "successful_tests": successful_tests,
                "total_tests": len(test_queries),
                "average_time_ms": avg_time
            }
            
        except Exception as e:
            self.log_result("qa_test", "error", f"Ошибка тестирования QA: {e}")
            return {"summary": f"Ошибка QA тестов: {e}", "test_results": []}
    
    async def run_document_stats_test(self) -> Dict[str, Any]:
        """Проверка статистики документов."""
        logger.info("📊 Проверка статистики документов")
        
        try:
            with get_session() as session:
                total_docs = session.query(Document).count()
                test_docs = session.query(Document).filter(
                    Document.metadata.op('->>')('created_for_testing') == 'true'
                ).count()
                
                self.log_result("stats_test", "success", f"Всего документов: {total_docs}, тестовых: {test_docs}")
                
                return {
                    "total_documents": total_docs,
                    "test_documents": test_docs,
                    "production_documents": total_docs - test_docs
                }
                
        except Exception as e:
            self.log_result("stats_test", "error", f"Ошибка получения статистики: {e}")
            return {"error": str(e)}
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Запуск всех тестов."""
        logger.info("🧪 Запуск полного набора тестов")
        self.stats["start_time"] = datetime.now()
        
        # QA тесты
        qa_results = await self.run_qa_tests()
        
        # Статистика документов
        stats_results = await self.run_document_stats_test()
        
        self.stats["end_time"] = datetime.now()
        
        return {
            "qa_tests": qa_results,
            "document_stats": stats_results,
            "summary": self._generate_summary("Завершены все тесты")
        }
    
    # === UTILITY METHODS ===
    
    def _generate_summary(self, main_message: str) -> Dict[str, Any]:
        """Генерация сводки результатов."""
        duration = None
        if self.stats["start_time"] and self.stats["end_time"]:
            duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
        
        return {
            "message": main_message,
            "statistics": self.stats.copy(),
            "duration_seconds": duration,
            "results": self.results[-10:],  # Последние 10 результатов
            "success_rate": (self.stats["successful"] / max(1, self.stats["processed"])) * 100
        }
    
    def save_report(self, results: Dict[str, Any], output_file: str = "document_report.json"):
        """Сохранение отчета."""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"💾 Отчет сохранен в {output_file}")
        
        # Краткий отчет в консоль
        print("\n" + "="*60)
        print("📄 ОТЧЕТ ПО ОБРАБОТКЕ ДОКУМЕНТОВ")
        print("="*60)
        print(f"📊 Обработано: {self.stats['processed']}")
        print(f"✅ Успешно: {self.stats['successful']}")
        print(f"❌ Ошибок: {self.stats['failed']}")
        print(f"⚠️ Пропущено: {self.stats['skipped']}")
        
        if results.get("duration_seconds"):
            print(f"⏱️ Время выполнения: {results['duration_seconds']:.1f}с")
        
        if results.get("success_rate"):
            print(f"📈 Успешность: {results['success_rate']:.1f}%")
        
        print(f"\n💾 Полный отчет: {output_file}")
        print("="*60)


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Document Loading Suite")
    parser.add_argument(
        "--mode", 
        choices=["pdf", "test", "run-tests", "full"], 
        default="test",
        help="Режим работы"
    )
    parser.add_argument(
        "--path", 
        help="Путь к директории с PDF файлами"
    )
    parser.add_argument(
        "--count", 
        type=int, 
        default=10,
        help="Количество тестовых документов"
    )
    parser.add_argument(
        "--max-files", 
        type=int,
        help="Максимальное количество PDF файлов для загрузки"
    )
    parser.add_argument(
        "--output", 
        default="document_report.json",
        help="Файл для отчета"
    )
    
    args = parser.parse_args()

    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    
    suite = DocumentSuite()
    
    try:
        if args.mode == "pdf":
            if not args.path:
                print("❌ Для режима 'pdf' требуется указать --path")
                sys.exit(1)
            results = await suite.load_pdf_batch(args.path, args.max_files)
            
        elif args.mode == "test":
            results = await suite.generate_test_documents(args.count)
            
        elif args.mode == "run-tests":
            results = await suite.run_all_tests()
            
        else:  # full
            # Комбинированный режим
            if args.path:
                logger.info("🚀 Полный режим: загрузка PDF + создание тестов + тестирование")
                pdf_results = await suite.load_pdf_batch(args.path, args.max_files)
                test_results = await suite.generate_test_documents(args.count)
                test_run_results = await suite.run_all_tests()
                
                results = {
                    "pdf_loading": pdf_results,
                    "test_generation": test_results,
                    "test_execution": test_run_results,
                    "summary": suite._generate_summary("Завершен полный цикл обработки")
                }
            else:
                # Только тесты
                test_results = await suite.generate_test_documents(args.count)
                test_run_results = await suite.run_all_tests()
                
                results = {
                    "test_generation": test_results,
                    "test_execution": test_run_results,
                    "summary": suite._generate_summary("Завершено тестирование")
                }
        
        suite.save_report(results, args.output)
        
        # Завершение с соответствующим кодом
        success_rate = results.get("success_rate", 0)
        if isinstance(results.get("summary"), dict):
            success_rate = results["summary"].get("success_rate", 0)
        
        sys.exit(0 if success_rate > 80 else 1)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
