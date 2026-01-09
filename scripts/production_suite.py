#!/usr/bin/env python3
"""
🚀 Production Management Suite
Объединенный инструмент для управления продакшн системой.

Включает функциональность из:
- production_startup.py
- production_startup_gemini.py  
- production_check_simplified.py

Использование:
    python -m scripts.production_suite --mode=startup
    python -m scripts.production_suite --mode=check
    python -m scripts.production_suite --mode=full
    python -m scripts.production_suite --mode=gemini
"""

import sys
import asyncio
import argparse
import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any

# Core imports
try:
    from sqlalchemy import text
    from core.infrastructure_suite import get_settings
    from core.storage_coordinator import create_storage_coordinator
    from core.ai_inference_suite import UnifiedAISystem
    from core.processing_pipeline import DocumentManager, RegulatoryPipeline
except ImportError as e:
    print(f"❌ Не удается импортировать core модули: {e}")
    sys.exit(1)

from core.logging_config import configure_logging


# Logging setup
configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


class ProductionSuite:
    """Объединенный инструмент для управления продакшн системой."""

    def __init__(self):
        """Инициализация suite."""
        self.config = get_settings()
        self.storage = None
        self.checks = []
        self.warnings = []
        self.failures = []
        self.performance_metrics = {}
        
    def add_success(self, component: str, message: str):
        """Добавить успешную проверку."""
        self.checks.append({"status": "success", "component": component, "message": message})
        logger.info(f"✅ {component}: {message}")
    
    def add_failure(self, component: str, message: str):
        """Добавить неуспешную проверку."""
        self.failures.append({"component": component, "message": message})
        logger.error(f"❌ {component}: {message}")
    
    def add_warning(self, component: str, message: str):
        """Добавить предупреждение."""
        self.warnings.append({"component": component, "message": message})
        logger.warning(f"⚠️ {component}: {message}")
    
    def add_performance_metric(self, metric: str, value: float, unit: str = "ms"):
        """Добавить метрику производительности."""
        self.performance_metrics[metric] = {"value": value, "unit": unit}
    
    # === ПРОВЕРКА КОНФИГУРАЦИИ ===
    
    def check_environment_variables(self) -> bool:
        """Проверка переменных окружения."""
        logger.info("🔍 Проверка переменных окружения...")
        
        required_vars = {
            "GEMINI_API_KEY": "Google Gemini API ключ",
            "TELEGRAM_BOT_TOKEN": "Токен Telegram бота",
            "DATABASE_URL": "URL базы данных PostgreSQL",
            "CHROMA_URL": "URL ChromaDB"
        }
        
        optional_vars = {
            "REDIS_URL": "URL Redis (опционально)",
            "LOG_LEVEL": "Уровень логирования"
        }
        
        all_valid = True
        
        # Проверка обязательных переменных
        for var, description in required_vars.items():
            value = os.getenv(var)
            if value:
                # Не показываем полные значения API ключей
                display_value = value[:10] + "..." if "KEY" in var or "TOKEN" in var else value
                self.add_success("Environment", f"{description}: {display_value}")
            else:
                self.add_failure("Environment", f"Отсутствует {description} ({var})")
                all_valid = False
        
        # Проверка опциональных переменных
        for var, description in optional_vars.items():
            value = os.getenv(var)
            if value:
                self.add_success("Environment", f"{description}: {value}")
            else:
                self.add_warning("Environment", f"Не установлено {description} ({var})")
        
        return all_valid
    
    def check_gemini_configuration(self) -> bool:
        """Проверка конфигурации Gemini."""
        logger.info("🤖 Проверка конфигурации Gemini...")
        
        try:
            import google.generativeai as genai
            
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                self.add_failure("Gemini", "API ключ не найден")
                return False
            
            # Настройка API
            genai.configure(api_key=api_key)
            
            # Проверка доступных моделей
            try:
                models = list(genai.list_models())
                available_models = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
                
                if available_models:
                    self.add_success("Gemini", f"Доступно моделей: {len(available_models)}")
                    
                    # Проверка конкретных моделей
                    preferred_models = [
                        "models/gemini-2.5-flash"
                    ]
                    
                    for model in preferred_models:
                        if model in available_models:
                            self.add_success("Gemini", f"Модель доступна: {model}")
                        else:
                            self.add_warning("Gemini", f"Модель недоступна: {model}")
                else:
                    self.add_failure("Gemini", "Модели недоступны")
                    return False
                    
            except Exception as e:
                self.add_failure("Gemini", f"Ошибка получения моделей: {e}")
                return False
            
            return True
            
        except ImportError:
            self.add_failure("Gemini", "Библиотека google-generativeai не установлена")
            return False
        except Exception as e:
            self.add_failure("Gemini", f"Ошибка конфигурации: {e}")
            return False
    
    def check_telegram_configuration(self) -> bool:
        """Проверка конфигурации Telegram."""
        logger.info("🤖 Проверка конфигурации Telegram...")
        
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            self.add_failure("Telegram", "Токен бота не найден")
            return False
        
        # Проверка формата токена
        if not token.count(':') == 1 or len(token.split(':')) < 8:
            self.add_failure("Telegram", "Неверный формат токена")
            return False
        
        self.add_success("Telegram", f"Токен настроен: {token[:10]}...")
        
        # Проверка доступности API (опционально)
        try:
            import requests
            response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get("ok"):
                    username = bot_info["result"].get("username", "unknown")
                    self.add_success("Telegram", f"Бот активен: @{username}")
                    return True
                else:
                    self.add_failure("Telegram", "Неверный токен бота")
                    return False
            else:
                self.add_warning("Telegram", "Не удается проверить токен")
                return True  # Предполагаем, что токен корректен
        except Exception as e:
            self.add_warning("Telegram", f"Проверка токена недоступна: {e}")
            return True
    
    # === ПРОВЕРКА БАЗЫ ДАННЫХ ===
    
    async def check_database_connectivity(self) -> bool:
        """Проверка подключения к базе данных."""
        logger.info("🗄️ Проверка базы данных...")

        if not self.storage or not hasattr(self.storage, 'postgres'):
            self.add_failure("Database", "Storage manager или postgres-менеджер не инициализирован.")
            return False

        try:
            start_time = time.time()
            
            async with self.storage.postgres.async_session_maker() as session:
                async with session.begin():
                    # Тест подключения
                    result = await session.execute(text("SELECT 1 as test"))
                    test_result = result.scalar_one_or_none()

                    if test_result == 1:
                        connection_time = (time.time() - start_time) * 1000
                        self.add_performance_metric("database_connection", connection_time, "ms")
                        self.add_success("Database", f"Подключение успешно ({connection_time:.1f}ms)")

                        # Проверка схемы
                        await self._check_database_schema(session)

                        # Статистика
                        await self._check_database_statistics(session)

                        return True
                    else:
                        self.add_failure("Database", "Тест подключения не прошел")
                        return False

        except Exception as e:
            self.add_failure("Database", f"Ошибка подключения: {e}")
            return False
    
    async def _check_database_schema(self, session):
        """Проверка схемы базы данных."""
        try:
            # Проверка основных таблиц
            tables_to_check = ["documents", "processing_results", "alembic_version"]
            
            for table_name in tables_to_check:
                try:
                    result = await session.execute(
                        text(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table_name}'")
                    )
                    table_exists = result.scalar_one() > 0
                    
                    if table_exists:
                        self.add_success("Database Schema", f"Таблица {table_name} существует")
                    else:
                        self.add_failure("Database Schema", f"Таблица {table_name} отсутствует")
                        
                except Exception as e:
                    self.add_failure("Database Schema", f"Ошибка проверки {table_name}: {e}")
                    
        except Exception as e:
            self.add_failure("Database Schema", f"Ошибка проверки схемы: {e}")
    
    async def _check_database_statistics(self, session):
        """Проверка статистики базы данных."""
        try:
            # Подсчет документов
            doc_count_result = await session.execute(text("SELECT COUNT(*) FROM documents"))
            doc_count = doc_count_result.scalar_one()
            self.add_success("Database Stats", f"Документов в БД: {doc_count}")
            
            if doc_count == 0:
                self.add_warning("Database Stats", "База данных пуста - загрузите документы")
            
            # Размер базы данных
            try:
                db_size_result = await session.execute(
                    text("SELECT pg_size_pretty(pg_database_size(current_database()))")
                )
                db_size = db_size_result.scalar()
                self.add_success("Database Stats", f"Размер БД: {db_size}")
            except Exception:
                self.add_warning("Database Stats", "Размер БД недоступен")
                
        except Exception as e:
            self.add_warning("Database Stats", f"Ошибка получения статистики: {e}")
    
    # === ПРОВЕРКА СЕРВИСОВ ===
    
    async def check_qa_service(self) -> bool:
        """Проверка QA сервиса."""
        logger.info("🔍 Проверка QA сервиса...")
        
        try:
            start_time = time.time()
            qa_service = UnifiedAISystem()
            init_time = (time.time() - start_time) * 1000
            
            self.add_performance_metric("qa_service_init", init_time, "ms")
            self.add_success("QA Service", f"Инициализация успешна ({init_time:.1f}ms)")
            
            # Тестовый поиск
            start_time = time.time()
            await qa_service.search_documents("тест", limit=1)
            search_time = (time.time() - start_time) * 1000
            
            self.add_performance_metric("qa_service_search", search_time, "ms")
            self.add_success("QA Service", f"Поиск работает ({search_time:.1f}ms)")
            
            return True
            
        except Exception as e:
            self.add_failure("QA Service", f"Ошибка инициализации: {e}")
            return False
    
    async def check_document_manager(self) -> bool:
        """Проверка Document Manager."""
        logger.info("📄 Проверка Document Manager...")
        
        try:
            start_time = time.time()
            DocumentManager()
            init_time = (time.time() - start_time) * 1000
            
            self.add_performance_metric("document_manager_init", init_time, "ms")
            self.add_success("Document Manager", f"Инициализация успешна ({init_time:.1f}ms)")
            
            return True
            
        except Exception as e:
            self.add_failure("Document Manager", f"Ошибка инициализации: {e}")
            return False
    
    async def check_regulatory_pipeline(self) -> bool:
        """Проверка Regulatory Pipeline."""
        logger.info("⚖️ Проверка Regulatory Pipeline...")
        
        try:
            start_time = time.time()
            RegulatoryPipeline()
            init_time = (time.time() - start_time) * 1000
            
            self.add_performance_metric("regulatory_pipeline_init", init_time, "ms")
            self.add_success("Regulatory Pipeline", f"Инициализация успешна ({init_time:.1f}ms)")
            
            return True
            
        except Exception as e:
            self.add_failure("Regulatory Pipeline", f"Ошибка инициализации: {e}")
            return False
    
    # === ПРОВЕРКА ПРОИЗВОДИТЕЛЬНОСТИ ===
    
    def check_performance_requirements(self) -> bool:
        """Проверка соответствия требованиям производительности."""
        logger.info("⚡ Проверка производительности...")
        
        performance_ok = True
        
        # Проверка времени подключения к БД
        db_time = self.performance_metrics.get("database_connection", {}).get("value", 0)
        if db_time > 1000:  # 1 секунда
            self.add_warning("Performance", f"Медленное подключение к БД: {db_time:.1f}ms")
            performance_ok = False
        else:
            self.add_success("Performance", f"Подключение к БД быстрое: {db_time:.1f}ms")
        
        # Проверка времени поиска
        search_time = self.performance_metrics.get("qa_service_search", {}).get("value", 0)
        if search_time > 2000:  # 2 секунды
            self.add_warning("Performance", f"Медленный поиск: {search_time:.1f}ms")
            performance_ok = False
        else:
            self.add_success("Performance", f"Поиск быстрый: {search_time:.1f}ms")
        
        return performance_ok
    
    # === ОСНОВНЫЕ МЕТОДЫ ===
    
    async def run_startup_checks(self) -> Dict[str, Any]:
        """Запуск проверок готовности к продакшн."""
        logger.info("🚀 Запуск проверок готовности к продакшн...")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "checks_passed": 0,
            "total_checks": 0,
            "all_systems_ready": True
        }
        
        # Инициализация хранилища
        self.storage = await create_storage_coordinator()
        
        # Конфигурация
        env_ok = self.check_environment_variables()
        gemini_ok = self.check_gemini_configuration()
        telegram_ok = self.check_telegram_configuration()
        
        # База данных
        db_ok = await self.check_database_connectivity()
        
        # Сервисы
        qa_ok = await self.check_qa_service()
        doc_manager_ok = await self.check_document_manager()
        pipeline_ok = await self.check_regulatory_pipeline()
        
        # Производительность
        perf_ok = self.check_performance_requirements()
        
        # Подсчет результатов
        checks = [env_ok, gemini_ok, telegram_ok, db_ok, qa_ok, doc_manager_ok, pipeline_ok, perf_ok]
        results["checks_passed"] = sum(checks)
        results["total_checks"] = len(checks)
        results["all_systems_ready"] = all(checks)
        
        # Добавляем детали
        results["success_checks"] = self.checks
        results["warnings"] = self.warnings
        results["failures"] = self.failures
        results["performance_metrics"] = self.performance_metrics
        
        return results
    
    async def run_simple_check(self) -> Dict[str, Any]:
        """Упрощенная проверка системы."""
        logger.info("🔍 Запуск упрощенной проверки...")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "status": "unknown"
        }
        
        # Инициализация хранилища
        self.storage = await create_storage_coordinator()
        
        # Основные проверки
        env_ok = self.check_environment_variables()
        db_ok = await self.check_database_connectivity()
        
        if env_ok and db_ok:
            results["status"] = "ready"
            self.add_success("System", "Система готова к работе")
        else:
            results["status"] = "not_ready"
            self.add_failure("System", "Система не готова")
        
        results["details"] = {
            "success_checks": self.checks,
            "warnings": self.warnings,
            "failures": self.failures
        }
        
        return results
    
    async def run_gemini_specific_checks(self) -> Dict[str, Any]:
        """Специфичные проверки для Gemini."""
        logger.info("🤖 Запуск Gemini-специфичных проверок...")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "gemini_ready": False
        }
        
        # Проверки Gemini
        api_ok = self.check_gemini_configuration()
        
        if api_ok:
            # Дополнительные проверки для Gemini
            try:
                import google.generativeai as genai
                
                # Тест генерации
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content("Тест: ответь 'OK'")
                
                if response and response.text:
                    self.add_success("Gemini Test", f"Генерация работает: {response.text[:50]}")
                    results["gemini_ready"] = True
                else:
                    self.add_failure("Gemini Test", "Генерация не работает")
                    
            except Exception as e:
                self.add_failure("Gemini Test", f"Ошибка тестирования: {e}")
        
        results["details"] = {
            "success_checks": self.checks,
            "warnings": self.warnings,
            "failures": self.failures
        }
        
        return results
    
    def generate_report(self, results: Dict[str, Any], output_file: str = "production_report.json"):
        """Генерация отчета."""
        logger.info(f"📊 Сохранение отчета в {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # Краткий отчет в консоль
        print("\n" + "="*60)
        print("🚀 ОТЧЕТ ПО ГОТОВНОСТИ ПРОДАКШН СИСТЕМЫ")
        print("="*60)
        
        if "all_systems_ready" in results:
            status_icon = "✅" if results["all_systems_ready"] else "❌"
            print(f"{status_icon} Система готова: {results['all_systems_ready']}")
            print(f"📊 Проверок пройдено: {results['checks_passed']}/{results['total_checks']}")
        
        if "status" in results:
            status_icon = "✅" if results["status"] == "ready" else "❌"
            print(f"{status_icon} Статус системы: {results['status']}")
        
        if "gemini_ready" in results:
            status_icon = "✅" if results["gemini_ready"] else "❌"
            print(f"{status_icon} Gemini готов: {results['gemini_ready']}")
        
        # Показать ошибки
        if self.failures:
            print(f"\n❌ Критические проблемы ({len(self.failures)}):")
            for failure in self.failures[:3]:
                print(f"  • {failure['component']}: {failure['message']}")
        
        # Показать предупреждения
        if self.warnings:
            print(f"\n⚠️ Предупреждения ({len(self.warnings)}):")
            for warning in self.warnings[:3]:
                print(f"  • {warning['component']}: {warning['message']}")
        
        print(f"\n💾 Полный отчет сохранен в: {output_file}")
        print("="*60)


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Production Management Suite")
    parser.add_argument(
        "--mode", 
        choices=["startup", "check", "gemini", "full"], 
        default="startup",
        help="Режим проверки"
    )
    parser.add_argument(
        "--output", 
        default="production_report.json",
        help="Файл для отчета"
    )
    
    args = parser.parse_args()
    
    suite = ProductionSuite()
    
    try:
        if args.mode == "startup":
            results = await suite.run_startup_checks()
        elif args.mode == "check":
            results = await suite.run_simple_check()
        elif args.mode == "gemini":
            results = await suite.run_gemini_specific_checks()
        else:  # full
            results = await suite.run_startup_checks()
        
        suite.generate_report(results, args.output)
        
        # Завершение с соответствующим кодом
        if "all_systems_ready" in results:
            sys.exit(0 if results["all_systems_ready"] else 1)
        elif "status" in results:
            sys.exit(0 if results["status"] == "ready" else 1)
        elif "gemini_ready" in results:
            sys.exit(0 if results["gemini_ready"] else 1)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
