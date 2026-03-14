#!/usr/bin/env python3
"""
Analysis & Diagnostics Suite
Объединенный инструмент для анализа и диагностики системы.

Включает функциональность из папок analysis/ и diagnostics/:
- analyze_documents.py, advanced_test.py, full_test.py
- check_chroma_config.py, check_database_status.py, etc.

Использование:
    python -m scripts.analysis_suite --mode=documents
    python -m scripts.analysis_suite --mode=database
    python -m scripts.analysis_suite --mode=chroma
    python -m scripts.analysis_suite --mode=search
    python -m scripts.analysis_suite --mode=full
"""

import sys
import asyncio
import argparse
import logging
import time
import json
from datetime import datetime
from typing import Dict, Any

# Core imports
try:
    from core.infrastructure_suite import get_settings
    from core.data_storage_suite import get_session, Document, engine
    from core.ai_inference_suite import UnifiedAISystem
    from core.processing_pipeline import DocumentManager
    from core.analysis_suite_utils import TextAnalyzer
    from core.logging_config import configure_logging
except ImportError as e:
    print(f" Не удается импортировать core модули: {e}")
    sys.exit(1)

# Database imports
try:
    from sqlalchemy import text, inspect
except ImportError as e:
    print(f" SQLAlchemy недоступен: {e}")

logger = logging.getLogger(__name__)


class AnalysisSuite:
    """Объединенный инструмент для анализа и диагностики."""
    
    def __init__(self):
        """Инициализация suite."""
        self.config = get_settings()
        self.analysis_results = {}
        self.diagnostics_results = {}
        self.start_time = datetime.now()
        
    def log_analysis(self, component: str, status: str, details: str, metrics: Dict[str, Any] = None):
        """Логирование результата анализа."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "status": status,
            "details": details,
            "metrics": metrics or {}
        }
        
        if component not in self.analysis_results:
            self.analysis_results[component] = []
        self.analysis_results[component].append(result)
        
        emoji = "" if status == "healthy" else "" if status == "critical" else ""
        logger.info(f"{emoji} {component}: {details}")
    
    # === DOCUMENT ANALYSIS ===
    
    async def analyze_documents(self) -> Dict[str, Any]:
        """Анализ документов в системе."""
        logger.info(" Анализ документов")
        
        analysis = {
            "total_documents": 0,
            "content_analysis": {},
            "metadata_analysis": {},
            "quality_metrics": {},
            "recommendations": []
        }
        
        try:
            with get_session() as session:
                # Базовая статистика
                documents = session.query(Document).all()
                analysis["total_documents"] = len(documents)
                
                if not documents:
                    self.log_analysis("documents", "warning", "Документы отсутствуют")
                    return analysis
                
                # Анализ содержимого
                content_lengths = []
                empty_content = 0
                short_content = 0
                
                for doc in documents:
                    content_len = len(doc.content or '')
                    content_lengths.append(content_len)
                    
                    if content_len == 0:
                        empty_content += 1
                    elif content_len < 100:
                        short_content += 1
                
                analysis["content_analysis"] = {
                    "avg_length": sum(content_lengths) / len(content_lengths) if content_lengths else 0,
                    "min_length": min(content_lengths) if content_lengths else 0,
                    "max_length": max(content_lengths) if content_lengths else 0,
                    "empty_documents": empty_content,
                    "short_documents": short_content,
                    "total_characters": sum(content_lengths)
                }
                
                # Анализ метаданных
                metadata_types = {}
                missing_metadata = 0
                
                for doc in documents:
                    if not doc.metadata:
                        missing_metadata += 1
                    else:
                        for key in doc.metadata.keys():
                            metadata_types[key] = metadata_types.get(key, 0) + 1
                
                analysis["metadata_analysis"] = {
                    "missing_metadata": missing_metadata,
                    "metadata_keys": metadata_types,
                    "coverage_percentage": ((len(documents) - missing_metadata) / len(documents)) * 100
                }
                
                # Метрики качества
                quality_score = 100
                
                # Штрафы за проблемы
                if empty_content > 0:
                    penalty = (empty_content / len(documents)) * 30
                    quality_score -= penalty
                    analysis["recommendations"].append(f"Удалить {empty_content} документов с пустым содержимым")
                
                if short_content > len(documents) * 0.2:
                    penalty = (short_content / len(documents)) * 15
                    quality_score -= penalty
                    analysis["recommendations"].append(f"Проверить {short_content} документов с коротким содержимым")
                
                if missing_metadata > len(documents) * 0.3:
                    penalty = (missing_metadata / len(documents)) * 20
                    quality_score -= penalty
                    analysis["recommendations"].append(f"Добавить метаданные к {missing_metadata} документам")
                
                analysis["quality_metrics"] = {
                    "quality_score": max(0, round(quality_score, 1)),
                    "health_status": "healthy" if quality_score > 80 else "warning" if quality_score > 60 else "critical"
                }
                
                # Типы документов
                doc_types = {}
                for doc in documents:
                    if doc.metadata and 'type' in doc.metadata:
                        doc_type = doc.metadata['type']
                        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                    else:
                        doc_types['unknown'] = doc_types.get('unknown', 0) + 1
                
                analysis["document_types"] = doc_types
                
                status = analysis["quality_metrics"]["health_status"]
                self.log_analysis(
                    "documents", 
                    status, 
                    f"Анализ {len(documents)} документов завершен. Качество: {analysis['quality_metrics']['quality_score']}/100",
                    analysis["quality_metrics"]
                )
                
                return analysis
                
        except Exception as e:
            self.log_analysis("documents", "critical", f"Ошибка анализа документов: {e}")
            return {"error": str(e)}
    
    # === DATABASE DIAGNOSTICS ===
    
    async def diagnose_database(self) -> Dict[str, Any]:
        """Диагностика состояния базы данных."""
        logger.info(" Диагностика базы данных")
        
        diagnostics = {
            "connection_status": "unknown",
            "schema_status": "unknown",
            "performance_metrics": {},
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Тест подключения
            start_time = time.time()
            with get_session() as session:
                result = session.execute(text("SELECT 1")).scalar()
                connection_time = (time.time() - start_time) * 1000
                
                if result == 1:
                    diagnostics["connection_status"] = "healthy"
                    diagnostics["performance_metrics"]["connection_time_ms"] = round(connection_time, 2)
                    
                    self.log_analysis(
                        "database_connection", 
                        "healthy", 
                        f"Подключение успешно ({connection_time:.1f}ms)"
                    )
                else:
                    diagnostics["connection_status"] = "critical"
                    diagnostics["issues"].append("Тест подключения не прошел")
                
                # Проверка схемы
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                
                required_tables = ["documents", "processing_results"]
                missing_tables = []
                
                for table in required_tables:
                    if table not in tables:
                        missing_tables.append(table)
                
                if missing_tables:
                    diagnostics["schema_status"] = "critical"
                    diagnostics["issues"].append(f"Отсутствуют таблицы: {', '.join(missing_tables)}")
                    diagnostics["recommendations"].append("Выполнить миграции базы данных")
                else:
                    diagnostics["schema_status"] = "healthy"
                    self.log_analysis("database_schema", "healthy", "Схема базы данных корректна")
                
                # Проверка индексов
                try:
                    indexes = inspector.get_indexes("documents")
                    index_names = [idx["name"] for idx in indexes]
                    
                    if not any("metadata" in name for name in index_names):
                        diagnostics["issues"].append("Отсутствует индекс на метаданные")
                        diagnostics["recommendations"].append("Создать индекс на поле metadata")
                    
                    diagnostics["performance_metrics"]["indexes_count"] = len(indexes)
                    
                except Exception as e:
                    diagnostics["issues"].append(f"Ошибка проверки индексов: {e}")
                
                # Статистика таблиц
                for table in ["documents", "processing_results"]:
                    if table in tables:
                        try:
                            count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                            diagnostics["performance_metrics"][f"{table}_count"] = count
                            
                            # Размер таблицы
                            size_query = text(f"SELECT pg_size_pretty(pg_total_relation_size('{table}'))")
                            size = session.execute(size_query).scalar()
                            diagnostics["performance_metrics"][f"{table}_size"] = size
                            
                        except Exception as e:
                            diagnostics["issues"].append(f"Ошибка получения статистики {table}: {e}")
                
                # Общий статус
                if diagnostics["connection_status"] == "healthy" and diagnostics["schema_status"] == "healthy":
                    overall_status = "healthy"
                elif "critical" in [diagnostics["connection_status"], diagnostics["schema_status"]]:
                    overall_status = "critical"
                else:
                    overall_status = "warning"
                
                self.log_analysis(
                    "database",
                    overall_status,
                    f"Диагностика БД завершена. Проблем: {len(diagnostics['issues'])}",
                    diagnostics["performance_metrics"]
                )
                
                return diagnostics
                
        except Exception as e:
            self.log_analysis("database", "critical", f"Критическая ошибка диагностики БД: {e}")
            return {"error": str(e), "connection_status": "critical"}
    
    # === CHROMA DIAGNOSTICS ===
    
    async def diagnose_chroma(self) -> Dict[str, Any]:
        """Диагностика ChromaDB."""
        logger.info(" Диагностика ChromaDB")
        
        diagnostics = {
            "availability": "unknown",
            "collections": [],
            "performance": {},
            "issues": [],
            "recommendations": []
        }
        
        try:
            import chromadb
            
            # Подключение к ChromaDB
            start_time = time.time()
            client = chromadb.Client()
            connection_time = (time.time() - start_time) * 1000
            
            diagnostics["availability"] = "available"
            diagnostics["performance"]["connection_time_ms"] = round(connection_time, 2)
            
            # Получение коллекций
            collections = client.list_collections()
            
            for collection in collections:
                try:
                    doc_count = collection.count()
                    
                    # Тест поиска
                    search_start = time.time()
                    collection.query(
                        query_texts=["тест"],
                        n_results=1
                    )
                    search_time = (time.time() - search_start) * 1000
                    
                    collection_info = {
                        "name": collection.name,
                        "document_count": doc_count,
                        "search_time_ms": round(search_time, 2)
                    }
                    
                    diagnostics["collections"].append(collection_info)
                    
                except Exception as e:
                    diagnostics["issues"].append(f"Ошибка анализа коллекции {collection.name}: {e}")
            
            # Оценка производительности
            if diagnostics["collections"]:
                avg_search_time = sum(c["search_time_ms"] for c in diagnostics["collections"]) / len(diagnostics["collections"])
                diagnostics["performance"]["avg_search_time_ms"] = round(avg_search_time, 2)
                
                if avg_search_time > 1000: # 1 секунда
                    diagnostics["issues"].append("Медленный поиск в ChromaDB")
                    diagnostics["recommendations"].append("Оптимизировать индексы ChromaDB")
            
            if not diagnostics["collections"]:
                diagnostics["issues"].append("Коллекции ChromaDB отсутствуют")
                diagnostics["recommendations"].append("Переиндексировать документы")
            
            # Общий статус
            if not diagnostics["issues"]:
                status = "healthy"
            elif any("критическая" in issue.lower() for issue in diagnostics["issues"]):
                status = "critical"
            else:
                status = "warning"
            
            self.log_analysis(
                "chroma",
                status,
                f"ChromaDB: {len(diagnostics['collections'])} коллекций, {len(diagnostics['issues'])} проблем"
            )
            
            return diagnostics
            
        except ImportError:
            diagnostics["availability"] = "unavailable"
            diagnostics["issues"].append("ChromaDB не установлен")
            self.log_analysis("chroma", "critical", "ChromaDB недоступен")
            return diagnostics
            
        except Exception as e:
            diagnostics["availability"] = "error"
            diagnostics["issues"].append(f"Ошибка подключения к ChromaDB: {e}")
            self.log_analysis("chroma", "critical", f"Ошибка ChromaDB: {e}")
            return diagnostics
    
    # === SEARCH SYSTEM DIAGNOSTICS ===
    
    async def diagnose_search_system(self) -> Dict[str, Any]:
        """Диагностика поисковой системы."""
        logger.info(" Диагностика поисковой системы")
        
        diagnostics = {
            "qa_service_status": "unknown",
            "search_tests": [],
            "performance": {},
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Инициализация QA сервиса
            start_time = time.time()
            qa_service = UnifiedAISystem()
            init_time = (time.time() - start_time) * 1000
            
            diagnostics["qa_service_status"] = "initialized"
            diagnostics["performance"]["init_time_ms"] = round(init_time, 2)
            
            # Тестовые запросы
            test_queries = [
                {"query": "тест", "expected_results": True, "description": "Простой поиск"},
                {"query": "федеральный закон", "expected_results": True, "description": "Специфичный поиск"},
                {"query": "несуществующий_термин_xyz123", "expected_results": False, "description": "Поиск без результатов"}
            ]
            
            total_search_time = 0
            successful_searches = 0
            
            for test in test_queries:
                try:
                    search_start = time.time()
                    results = await qa_service.search_documents(test["query"], limit=5)
                    search_time = (time.time() - search_start) * 1000
                    total_search_time += search_time
                    
                    has_results = bool(results and len(results) > 0)
                    test_passed = has_results == test["expected_results"]
                    
                    if test_passed:
                        successful_searches += 1
                    
                    test_result = {
                        "query": test["query"],
                        "description": test["description"],
                        "expected_results": test["expected_results"],
                        "actual_results": has_results,
                        "results_count": len(results) if results else 0,
                        "search_time_ms": round(search_time, 2),
                        "passed": test_passed
                    }
                    
                    diagnostics["search_tests"].append(test_result)
                    
                except Exception as e:
                    diagnostics["issues"].append(f"Ошибка поиска '{test['query']}': {e}")
                    diagnostics["search_tests"].append({
                        "query": test["query"],
                        "description": test["description"],
                        "error": str(e),
                        "passed": False
                    })
            
            # Метрики производительности
            if successful_searches > 0:
                avg_search_time = total_search_time / len(test_queries)
                diagnostics["performance"]["avg_search_time_ms"] = round(avg_search_time, 2)
                diagnostics["performance"]["success_rate"] = (successful_searches / len(test_queries)) * 100
                
                # Анализ производительности
                if avg_search_time > 2000: # 2 секунды
                    diagnostics["issues"].append("Медленный поиск документов")
                    diagnostics["recommendations"].append("Оптимизировать поисковые алгоритмы")
                
                if successful_searches < len(test_queries) * 0.8:
                    diagnostics["issues"].append("Низкая успешность поиска")
                    diagnostics["recommendations"].append("Проверить качество индексации")
            
            # Общий статус
            if not diagnostics["issues"] and successful_searches == len(test_queries):
                status = "healthy"
            elif successful_searches == 0:
                status = "critical"
            else:
                status = "warning"
            
            self.log_analysis(
                "search_system",
                status,
                f"Поисковая система: {successful_searches}/{len(test_queries)} тестов пройдено"
            )
            
            return diagnostics
            
        except Exception as e:
            diagnostics["qa_service_status"] = "error"
            diagnostics["issues"].append(f"Критическая ошибка поисковой системы: {e}")
            self.log_analysis("search_system", "critical", f"Ошибка поисковой системы: {e}")
            return diagnostics
    
    # === MAIN METHODS ===
    
    async def run_document_analysis(self) -> Dict[str, Any]:
        """Запуск анализа документов."""
        logger.info(" Запуск анализа документов")
        
        documents_analysis = await self.analyze_documents()
        
        return {
            "analysis_type": "documents",
            "timestamp": datetime.now().isoformat(),
            "results": documents_analysis,
            "summary": self.analysis_results
        }
    
    async def run_database_diagnostics(self) -> Dict[str, Any]:
        """Запуск диагностики базы данных."""
        logger.info(" Запуск диагностики базы данных")
        
        database_diagnostics = await self.diagnose_database()
        
        return {
            "analysis_type": "database",
            "timestamp": datetime.now().isoformat(),
            "results": database_diagnostics,
            "summary": self.analysis_results
        }
    
    async def run_chroma_diagnostics(self) -> Dict[str, Any]:
        """Запуск диагностики ChromaDB."""
        logger.info(" Запуск диагностики ChromaDB")
        
        chroma_diagnostics = await self.diagnose_chroma()
        
        return {
            "analysis_type": "chroma",
            "timestamp": datetime.now().isoformat(),
            "results": chroma_diagnostics,
            "summary": self.analysis_results
        }
    
    async def run_search_diagnostics(self) -> Dict[str, Any]:
        """Запуск диагностики поисковой системы."""
        logger.info(" Запуск диагностики поиска")
        
        search_diagnostics = await self.diagnose_search_system()
        
        return {
            "analysis_type": "search",
            "timestamp": datetime.now().isoformat(),
            "results": search_diagnostics,
            "summary": self.analysis_results
        }
    
    async def run_full_analysis(self) -> Dict[str, Any]:
        """Запуск полного анализа системы."""
        logger.info(" Запуск полного анализа системы")
        
        # Анализ документов
        documents_analysis = await self.analyze_documents()
        
        # Диагностика базы данных
        database_diagnostics = await self.diagnose_database()
        
        # Диагностика ChromaDB
        chroma_diagnostics = await self.diagnose_chroma()
        
        # Диагностика поиска
        search_diagnostics = await self.diagnose_search_system()
        
        # Общая оценка системы
        all_components = [
            documents_analysis.get("quality_metrics", {}).get("health_status", "unknown"),
            "healthy" if database_diagnostics.get("connection_status") == "healthy" else "critical",
            "healthy" if chroma_diagnostics.get("availability") == "available" else "warning",
            "healthy" if not search_diagnostics.get("issues") else "warning"
        ]
        
        healthy_components = sum(1 for status in all_components if status == "healthy")
        system_health_percentage = (healthy_components / len(all_components)) * 100
        
        if system_health_percentage > 75:
            overall_health = "healthy"
        elif system_health_percentage > 50:
            overall_health = "warning"
        else:
            overall_health = "critical"
        
        return {
            "analysis_type": "full",
            "timestamp": datetime.now().isoformat(),
            "results": {
                "documents": documents_analysis,
                "database": database_diagnostics,
                "chroma": chroma_diagnostics,
                "search": search_diagnostics
            },
            "system_health": {
                "overall_status": overall_health,
                "health_percentage": round(system_health_percentage, 1),
                "component_statuses": dict(zip(["documents", "database", "chroma", "search"], all_components))
            },
            "summary": self.analysis_results
        }
    
    def generate_report(self, results: Dict[str, Any], output_file: str = "analysis_report.json"):
        """Генерация отчета анализа."""
        # Добавление информации о сессии
        results["session_info"] = {
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "components_analyzed": len(self.analysis_results),
            "total_checks": sum(len(checks) for checks in self.analysis_results.values())
        }
        
        # Сохранение в файл
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        # Краткий отчет
        print("\n" + "="*60)
        print(" ОТЧЕТ ПО АНАЛИЗУ СИСТЕМЫ")
        print("="*60)
        
        analysis_type = results.get("analysis_type", "unknown")
        print(f" Тип анализа: {analysis_type}")
        print(f" Продолжительность: {results['session_info']['duration_seconds']:.1f}с")
        print(f" Компонентов проанализировано: {results['session_info']['components_analyzed']}")
        
        # Показать ключевые метрики
        if "system_health" in results:
            health = results["system_health"]
            print(f" Общее состояние системы: {health['overall_status']} ({health['health_percentage']}%)")
            
            for component, status in health["component_statuses"].items():
                emoji = "" if status == "healthy" else "" if status == "critical" else ""
                print(f" {emoji} {component}: {status}")
        
        elif "results" in results:
            # Показать специфичные результаты
            if analysis_type == "documents":
                quality = results["results"].get("quality_metrics", {})
                if quality:
                    print(f" Качество документов: {quality.get('quality_score', 0)}/100")
            
            elif analysis_type == "database":
                db_status = results["results"].get("connection_status", "unknown")
                print(f" Статус БД: {db_status}")
            
        print(f"\n Полный отчет сохранен в: {output_file}")
        print("="*60)


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Analysis & Diagnostics Suite")
    parser.add_argument(
        "--mode", 
        choices=["documents", "database", "chroma", "search", "full"], 
        default="full",
        help="Режим анализа"
    )
    parser.add_argument(
        "--output", 
        default="analysis_report.json",
        help="Файл для отчета"
    )
    
    args = parser.parse_args()

    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    
    suite = AnalysisSuite()
    
    try:
        if args.mode == "documents":
            results = await suite.run_document_analysis()
        elif args.mode == "database":
            results = await suite.run_database_diagnostics()
        elif args.mode == "chroma":
            results = await suite.run_chroma_diagnostics()
        elif args.mode == "search":
            results = await suite.run_search_diagnostics()
        else: # full
            results = await suite.run_full_analysis()
        
        suite.generate_report(results, args.output)
        
        # Определение кода завершения
        if "system_health" in results:
            health_status = results["system_health"]["overall_status"]
            sys.exit(0 if health_status == "healthy" else 1)
        elif "results" in results and "error" not in results["results"]:
            sys.exit(0)
        else:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f" Критическая ошибка анализа: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
