#!/usr/bin/env python3
"""
Utilities Suite
Объединенный инструмент для вспомогательных операций.

Включает оставшиеся утилиты:
- docker_manager.py
- manual_bot_test.py

Использование:
    python -m scripts.utilities_suite --mode=docker --action=build
    python -m scripts.utilities_suite --mode=docker --action=start
    python -m scripts.utilities_suite --mode=bot-test
    python -m scripts.utilities_suite --mode=health-check
"""

import sys
import asyncio
import argparse
import logging
import subprocess
import json
from datetime import datetime
from typing import Dict, Any

# Core imports
try:
    from core.infrastructure_suite import get_settings, get_core_app
    from core.storage_coordinator import create_storage_coordinator
except ImportError as e:
    print(f" Не удается импортировать core модули: {e}")
    sys.exit(1)

# Telegram imports (для тестирования бота)
try:
    import requests
except ImportError:
    requests = None

# Logging setup
from core.logging_config import configure_logging


class UtilitiesSuite:
    """Объединенный инструмент для вспомогательных операций."""

    def __init__(self, storage_manager=None):
        """Инициализация suite."""
        self.config = get_settings()
        self.storage_manager = storage_manager
        self.operations = []
        self.start_time = datetime.now()
        
    def log_operation(self, operation: str, status: str, details: str):
        """Логирование операции."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "status": status,
            "details": details
        }
        self.operations.append(result)
        
        emoji = "" if status == "success" else "" if status == "error" else ""
        logger.info(f"{emoji} {operation}: {details}")
    
    # === DOCKER MANAGEMENT ===
    
    def check_docker_installation(self) -> bool:
        """Проверка установки Docker."""
        try:
            result = subprocess.run(
                ["docker", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                self.log_operation("docker_check", "success", f"Docker установлен: {version}")
                return True
            else:
                self.log_operation("docker_check", "error", "Docker не отвечает")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_operation("docker_check", "error", "Timeout при проверке Docker")
            return False
        except FileNotFoundError:
            self.log_operation("docker_check", "error", "Docker не найден в системе")
            return False
        except Exception as e:
            self.log_operation("docker_check", "error", f"Ошибка проверки Docker: {e}")
            return False
    
    def check_docker_compose(self) -> bool:
        """Проверка Docker Compose."""
        try:
            result = subprocess.run(
                ["docker-compose", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                self.log_operation("compose_check", "success", f"Docker Compose: {version}")
                return True
            else:
                # Пробуем новый формат команды
                result = subprocess.run(
                    ["docker", "compose", "version"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                
                if result.returncode == 0:
                    version = result.stdout.strip()
                    self.log_operation("compose_check", "success", f"Docker Compose (новый): {version}")
                    return True
                else:
                    self.log_operation("compose_check", "error", "Docker Compose недоступен")
                    return False
                    
        except Exception as e:
            self.log_operation("compose_check", "error", f"Ошибка проверки Compose: {e}")
            return False
    
    def build_docker_services(self) -> Dict[str, Any]:
        """Сборка Docker сервисов."""
        logger.info(" Сборка Docker сервисов")
        
        if not self.check_docker_installation():
            return {"error": "Docker недоступен"}
        
        if not self.check_docker_compose():
            return {"error": "Docker Compose недоступен"}
        
        try:
            # Сборка сервисов
            result = subprocess.run(
                ["docker-compose", "build"],
                capture_output=True,
                text=True,
                timeout=600 # 10 минут
            )
            
            if result.returncode == 0:
                self.log_operation("docker_build", "success", "Сборка Docker сервисов завершена")
                
                return {
                    "success": True,
                    "message": "Docker сервисы собраны успешно",
                    "output": result.stdout
                }
            else:
                self.log_operation("docker_build", "error", f"Ошибка сборки: {result.stderr}")
                
                return {
                    "success": False,
                    "error": result.stderr,
                    "output": result.stdout
                }
                
        except subprocess.TimeoutExpired:
            self.log_operation("docker_build", "error", "Timeout при сборке Docker")
            return {"error": "Timeout при сборке Docker сервисов"}
        except Exception as e:
            self.log_operation("docker_build", "error", f"Исключение при сборке: {e}")
            return {"error": str(e)}
    
    def start_docker_services(self) -> Dict[str, Any]:
        """Запуск Docker сервисов."""
        logger.info(" Запуск Docker сервисов")
        
        if not self.check_docker_installation():
            return {"error": "Docker недоступен"}
        
        try:
            # Запуск сервисов
            result = subprocess.run(
                ["docker-compose", "up", "-d"],
                capture_output=True,
                text=True,
                timeout=120 # 2 минуты
            )
            
            if result.returncode == 0:
                self.log_operation("docker_start", "success", "Docker сервисы запущены")
                
                # Проверка статуса сервисов
                status_result = subprocess.run(
                    ["docker-compose", "ps"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                return {
                    "success": True,
                    "message": "Docker сервисы запущены",
                    "output": result.stdout,
                    "status": status_result.stdout if status_result.returncode == 0 else "Статус недоступен"
                }
            else:
                self.log_operation("docker_start", "error", f"Ошибка запуска: {result.stderr}")
                
                return {
                    "success": False,
                    "error": result.stderr,
                    "output": result.stdout
                }
                
        except subprocess.TimeoutExpired:
            self.log_operation("docker_start", "error", "Timeout при запуске Docker")
            return {"error": "Timeout при запуске Docker сервисов"}
        except Exception as e:
            self.log_operation("docker_start", "error", f"Исключение при запуске: {e}")
            return {"error": str(e)}
    
    def stop_docker_services(self) -> Dict[str, Any]:
        """Остановка Docker сервисов."""
        logger.info(" Остановка Docker сервисов")
        
        try:
            result = subprocess.run(
                ["docker-compose", "down"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.log_operation("docker_stop", "success", "Docker сервисы остановлены")
                
                return {
                    "success": True,
                    "message": "Docker сервисы остановлены",
                    "output": result.stdout
                }
            else:
                self.log_operation("docker_stop", "error", f"Ошибка остановки: {result.stderr}")
                
                return {
                    "success": False,
                    "error": result.stderr,
                    "output": result.stdout
                }
                
        except subprocess.TimeoutExpired:
            self.log_operation("docker_stop", "error", "Timeout при остановке Docker")
            return {"error": "Timeout при остановке Docker сервисов"}
        except Exception as e:
            self.log_operation("docker_stop", "error", f"Исключение при остановке: {e}")
            return {"error": str(e)}
    
    def get_docker_status(self) -> Dict[str, Any]:
        """Получение статуса Docker сервисов."""
        logger.info(" Проверка статуса Docker сервисов")
        
        if not self.check_docker_installation():
            return {"error": "Docker недоступен"}
        
        try:
            # Статус сервисов
            result = subprocess.run(
                ["docker-compose", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                try:
                    # Парсинг JSON вывода
                    services = []
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            services.append(json.loads(line))
                    
                    self.log_operation("docker_status", "success", f"Статус {len(services)} сервисов получен")
                    
                    return {
                        "success": True,
                        "services": services,
                        "running_count": len([s for s in services if s.get("State") == "running"]),
                        "total_count": len(services)
                    }
                    
                except json.JSONDecodeError:
                    # Fallback к текстовому формату
                    text_result = subprocess.run(
                        ["docker-compose", "ps"],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    return {
                        "success": True,
                        "status_text": text_result.stdout,
                        "message": "Статус получен в текстовом формате"
                    }
            else:
                self.log_operation("docker_status", "error", f"Ошибка получения статуса: {result.stderr}")
                return {"error": result.stderr}
                
        except Exception as e:
            self.log_operation("docker_status", "error", f"Исключение при проверке статуса: {e}")
            return {"error": str(e)}
    
    # === BOT TESTING ===
    
    def test_telegram_bot(self) -> Dict[str, Any]:
        """Тестирование Telegram бота."""
        logger.info(" Тестирование Telegram бота")
        
        if not requests:
            self.log_operation("bot_test", "error", "Библиотека requests недоступна")
            return {"error": "requests недоступен"}
        
        # Получение токена бота
        bot_token = self.config.TELEGRAM_BOT_TOKEN if hasattr(self.config, 'TELEGRAM_BOT_TOKEN') else None
        
        if not bot_token:
            import os
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        
        if not bot_token:
            self.log_operation("bot_test", "error", "Токен Telegram бота не найден")
            return {"error": "Токен бота недоступен"}
        
        tests = {
            "bot_info": {"passed": False, "details": ""},
            "webhook_info": {"passed": False, "details": ""},
            "commands": {"passed": False, "details": ""}
        }
        
        try:
            # Тест 1: Получение информации о боте
            response = requests.get(
                f"https://api.telegram.org/bot{bot_token}/getMe",
                timeout=10
            )
            
            if response.status_code == 200:
                bot_data = response.json()
                if bot_data.get("ok"):
                    bot_info = bot_data["result"]
                    username = bot_info.get("username", "unknown")
                    tests["bot_info"]["passed"] = True
                    tests["bot_info"]["details"] = f"Бот @{username} активен"
                    self.log_operation("bot_info", "success", f"Бот @{username} активен")
                else:
                    tests["bot_info"]["details"] = "Неверный токен бота"
                    self.log_operation("bot_info", "error", "Неверный токен бота")
            else:
                tests["bot_info"]["details"] = f"HTTP {response.status_code}"
                self.log_operation("bot_info", "error", f"HTTP ошибка: {response.status_code}")
            
            # Тест 2: Проверка webhook
            response = requests.get(
                f"https://api.telegram.org/bot{bot_token}/getWebhookInfo",
                timeout=10
            )
            
            if response.status_code == 200:
                webhook_data = response.json()
                if webhook_data.get("ok"):
                    webhook_info = webhook_data["result"]
                    webhook_url = webhook_info.get("url", "")
                    
                    if webhook_url:
                        tests["webhook_info"]["passed"] = True
                        tests["webhook_info"]["details"] = f"Webhook: {webhook_url[:50]}..."
                        self.log_operation("webhook_check", "success", "Webhook настроен")
                    else:
                        tests["webhook_info"]["passed"] = True
                        tests["webhook_info"]["details"] = "Polling режим"
                        self.log_operation("webhook_check", "success", "Polling режим")
            
            # Тест 3: Получение команд бота
            response = requests.get(
                f"https://api.telegram.org/bot{bot_token}/getMyCommands",
                timeout=10
            )
            
            if response.status_code == 200:
                commands_data = response.json()
                if commands_data.get("ok"):
                    commands = commands_data["result"]
                    tests["commands"]["passed"] = True
                    tests["commands"]["details"] = f"Команд настроено: {len(commands)}"
                    self.log_operation("bot_commands", "success", f"Команд: {len(commands)}")
            
            # Общий результат
            passed_tests = sum(1 for test in tests.values() if test["passed"])
            success_rate = (passed_tests / len(tests)) * 100
            
            return {
                "success": success_rate > 50,
                "tests": tests,
                "passed_tests": passed_tests,
                "total_tests": len(tests),
                "success_rate": success_rate
            }
            
        except requests.RequestException as e:
            self.log_operation("bot_test", "error", f"Ошибка сети: {e}")
            return {"error": f"Ошибка сети: {e}"}
        except Exception as e:
            self.log_operation("bot_test", "error", f"Исключение: {e}")
            return {"error": str(e)}
    
    # === HEALTH CHECK ===
    
    def run_system_health_check(self) -> Dict[str, Any]:
        """Проверка общего состояния системы."""
        logger.info(" Проверка состояния системы")
        
        health_checks = {
            "docker_available": False,
            "environment_configured": False,
            "bot_accessible": False,
            "services_running": False,
            "database_connected": False,
            "redis_connected": False,
            "vector_store_connected": False,
        }
        
        details = {}
        
        # Проверка Docker
        if self.check_docker_installation():
            health_checks["docker_available"] = True
            details["docker"] = "Docker доступен"
        else:
            details["docker"] = "Docker недоступен"
        
        # Проверка переменных окружения
        import os
        required_vars = ["TELEGRAM_BOT_TOKEN", "DATABASE_URL", "GEMINI_API_KEY"]
        configured_vars = sum(1 for var in required_vars if os.getenv(var))
        
        if configured_vars >= len(required_vars) * 0.75: # 75% переменных настроены
            health_checks["environment_configured"] = True
            details["environment"] = f"Настроено {configured_vars}/{len(required_vars)} переменных"
        else:
            details["environment"] = f"Недостаточно переменных: {configured_vars}/{len(required_vars)}"
        
        # Проверка бота
        bot_test = self.test_telegram_bot()
        if not bot_test.get("error") and bot_test.get("success"):
            health_checks["bot_accessible"] = True
            details["bot"] = "Telegram бот доступен"
        else:
            details["bot"] = "Telegram бот недоступен"
        
        # Проверка Docker сервисов
        if health_checks["docker_available"]:
            docker_status = self.get_docker_status()
            if docker_status.get("success"):
                running_count = docker_status.get("running_count", 0)
                total_count = docker_status.get("total_count", 0)
                
                if running_count > 0:
                    health_checks["services_running"] = True
                    details["services"] = f"Запущено {running_count}/{total_count} сервисов"
                else:
                    details["services"] = "Сервисы не запущены"
            else:
                details["services"] = "Статус сервисов недоступен"
        else:
            details["services"] = "Docker недоступен"
        
        # Проверка хранилищ
        if self.storage_manager:
            storage_health = self.storage_manager.get_health_status()
            health_checks["database_connected"] = storage_health.get("postgres", {}).get("connected", False)
            health_checks["redis_connected"] = storage_health.get("redis", {}).get("connected", False)
            health_checks["vector_store_connected"] = storage_health.get("vector_store", {}).get("connected", False)
            details["database"] = "PostgreSQL подключен" if health_checks["database_connected"] else "PostgreSQL недоступен"
            details["redis"] = "Redis подключен" if health_checks["redis_connected"] else "Redis недоступен"
            details["vector_store"] = "Vector Store подключен" if health_checks["vector_store_connected"] else "Vector Store недоступен"
        else:
            details["database"] = "Storage manager не инициализирован"
            details["redis"] = "Storage manager не инициализирован"
            details["vector_store"] = "Storage manager не инициализирован"

        # Общая оценка здоровья
        healthy_checks = sum(health_checks.values())
        total_checks = len(health_checks)
        health_percentage = (healthy_checks / total_checks) * 100
        
        if health_percentage >= 75:
            overall_status = "healthy"
        elif health_percentage >= 50:
            overall_status = "warning"
        else:
            overall_status = "critical"
        
        self.log_operation(
            "health_check",
            "success" if overall_status == "healthy" else "warning",
            f"Система {overall_status}: {healthy_checks}/{total_checks} проверок пройдено"
        )
        
        return {
            "overall_status": overall_status,
            "health_percentage": round(health_percentage, 1),
            "checks": health_checks,
            "details": details,
            "passed_checks": healthy_checks,
            "total_checks": total_checks
        }
    
    # === MAIN METHODS ===
    
    def generate_report(self, results: Dict[str, Any], output_file: str = "utilities_report.json"):
        """Генерация отчета утилит."""
        # Добавление информации о сессии
        results["session_info"] = {
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "total_operations": len(self.operations),
            "successful_operations": len([op for op in self.operations if op["status"] == "success"])
        }
        
        # Сохранение в файл
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        # Краткий отчет
        print("\n" + "="*60)
        print(" ОТЧЕТ ПО УТИЛИТАМ")
        print("="*60)
        
        session_info = results["session_info"]
        print(f" Продолжительность: {session_info['duration_seconds']:.1f}с")
        print(f" Успешных операций: {session_info['successful_operations']}")
        print(f" Всего операций: {session_info['total_operations']}")
        
        # Специфичная информация
        if "overall_status" in results:
            health = results["overall_status"]
            percentage = results.get("health_percentage", 0)
            print(f" Состояние системы: {health} ({percentage}%)")
        
        print(f"\n Полный отчет сохранен в: {output_file}")
        print("="*60)


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Utilities Suite")
    parser.add_argument(
        "--mode", 
        choices=["docker", "bot-test", "health-check"], 
        default="health-check",
        help="Режим работы"
    )
    parser.add_argument(
        "--action", 
        choices=["build", "start", "stop", "status"], 
        help="Действие для Docker (только для mode=docker)"
    )
    parser.add_argument(
        "--output", 
        default="utilities_report.json",
        help="Файл для отчета"
    )
    
    args = parser.parse_args()
    
    configure_logging()

    core_app = get_core_app()
    await core_app.initialize()

    storage_manager = None
    if args.mode == "health-check":
        try:
            storage_manager = await create_storage_coordinator()
            core_app.register_component("storage", storage_manager)
        except Exception as e:
            logger.warning(f" Не удалось инициализировать storage manager: {e}")

    suite = UtilitiesSuite(storage_manager=storage_manager)

    try:
        if args.mode == "docker":
            if not args.action:
                print(" Для режима 'docker' требуется указать --action")
                sys.exit(1)

            if args.action == "build":
                results = suite.build_docker_services()
            elif args.action == "start":
                results = suite.start_docker_services()
            elif args.action == "stop":
                results = suite.stop_docker_services()
            elif args.action == "status":
                results = suite.get_docker_status()

        elif args.mode == "bot-test":
            results = suite.test_telegram_bot()

        else: # health-check
            results = suite.run_system_health_check()

        suite.generate_report(results, args.output)
        
        # Определение кода завершения
        if "success" in results:
            sys.exit(0 if results["success"] else 1)
        elif "overall_status" in results:
            status = results["overall_status"]
            sys.exit(0 if status == "healthy" else 1)
        else:
            sys.exit(0)
        
    except Exception as e:
        logger.error(f" Критическая ошибка утилит: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
