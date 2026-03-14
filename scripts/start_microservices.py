#!/usr/bin/env python3
"""
LegalRAG Microservices Startup Script
Запуск всех микросервисов через оркестратор
"""

import asyncio
import sys
import signal
import argparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from services.orchestrator import ServicesOrchestrator


async def main():
    """Основная функция запуска микросервисов"""
    
    parser = argparse.ArgumentParser(description='LegalRAG Microservices')
    parser.add_argument('--host', default='0.0.0.0', help='Gateway host')
    parser.add_argument('--port', type=int, default=8080, help='Gateway port')
    parser.add_argument('--no-gateway', action='store_true', help='Start without gateway')
    
    args = parser.parse_args()
    
    # Создаем оркестратор
    orchestrator = ServicesOrchestrator()
    
    # Обработка сигналов завершения
    def signal_handler(signum, frame):
        print(f"\n Получен сигнал {signum}, завершение работы...")
        orchestrator.shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        print(" Запуск LegalRAG Microservices...")
        
        # Обновляем конфигурацию из аргументов
        orchestrator.config.update({
            "gateway_host": args.host,
            "gateway_port": args.port,
            "start_gateway": not args.no_gateway
        })
        
        # Запуск всех сервисов
        await orchestrator.start_all_services()
        
        print(" Все микросервисы запущены успешно!")
        print(f" API Gateway доступен на: http://{args.host}:{args.port}")
        print(" Health check: http://{host}:{port}/health".format(host=args.host, port=args.port))
        
        # Запуск API Gateway сервера
        if not args.no_gateway:
            print(" Запуск API Gateway сервера...")
            await orchestrator.run_server()
        else:
            # Ожидание сигнала завершения без gateway
            await orchestrator.shutdown_event.wait()
        
    except Exception as e:
        print(f" Ошибка при запуске микросервисов: {e}")
        sys.exit(1)
    
    finally:
        print("\n Завершение работы микросервисов...")
        await orchestrator.shutdown_all_services()
        print(" Все сервисы остановлены")


if __name__ == "__main__":
    # Запуск с обработкой исключений
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Завершение по Ctrl+C")
    except Exception as e:
        print(f" Критическая ошибка: {e}")
        sys.exit(1)