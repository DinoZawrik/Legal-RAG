#!/usr/bin/env python3
"""
Document Worker Startup Script
Запуск background worker'а для обработки документов через Task Queue
"""

import argparse
import asyncio
import logging
import signal
import sys
import os
from pathlib import Path
from typing import Optional

# Добавляем корневую папку проекта в PYTHONPATH
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.document_worker import start_document_worker
from core.logging_config import configure_logging

# Настройка логирования
# logging.basicConfig(
# level=logging.INFO,
# format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
# handlers=[
# logging.StreamHandler(sys.stdout),
# logging.FileHandler('logs/document_worker.log') if os.path.exists('logs') else logging.NullHandler()
# ]
# )

logger = logging.getLogger(__name__)

class WorkerManager:
    """Менеджер для управления document worker'ом"""
    
    def __init__(self):
        self.worker_task = None
        self.shutdown_event = asyncio.Event()
    
    async def start(self):
        """Запуск worker'а"""
        worker_id = os.getenv('WORKER_ID', 'main-document-worker')
        
        logger.info(f" Starting Document Worker: {worker_id}")
        
        # Устанавливаем обработчики сигналов для graceful shutdown
        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, self._signal_handler)
        
        # Запускаем worker в отдельной задаче
        self.worker_task = asyncio.create_task(
            start_document_worker(worker_id)
        )
        
        try:
            # Ждем завершения worker'а или сигнала shutdown
            await asyncio.gather(
                self.worker_task,
                self._wait_for_shutdown(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f" Worker error: {e}")
        finally:
            logger.info(" Document Worker shutdown completed")
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f" Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()
        
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
    
    async def _wait_for_shutdown(self):
        """Ожидание сигнала завершения"""
        await self.shutdown_event.wait()


async def main():
    """Основная функция запуска worker'а"""
    logger.info(" Document Worker starting...")
    
    # Проверяем переменные окружения
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    logger.info(f" Redis URL: {redis_url}")
    
    # Создаем и запускаем менеджер worker'а
    manager = WorkerManager()
    await manager.start()


if __name__ == "__main__":
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    asyncio.run(main())