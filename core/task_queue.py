#!/usr/bin/env python3
"""
Task Queue System
Система управления фоновыми задачами на основе Redis
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Статусы задач."""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Приоритеты задач."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Task:
    """Задача в очереди."""
    task_id: str
    task_type: str
    data: Dict[str, Any]
    status: Any = None # Будет конвертирован в TaskStatus в __post_init__
    priority: Any = None # Будет конвертирован в TaskPriority в __post_init__
    created_at: float = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    progress_messages: List[Dict[str, Any]] = None
    progress: int = 0 # 0-100%
    result: Optional[Dict[str, Any]] = None
    worker_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        # Обрабатываем created_at
        if self.created_at is None:
            self.created_at = time.time()
        if self.progress_messages is None:
            self.progress_messages = []
        
        # Конвертируем status в enum
        if self.status is None:
            self.status = TaskStatus.PENDING
        elif isinstance(self.status, str):
            if self.status.startswith('TaskStatus.'):
                # Извлекаем значение из строки "TaskStatus.PENDING" -> "pending"
                status_name = self.status.split('.')[-1].lower()
                self.status = TaskStatus(status_name)
            else:
                # Если это уже правильный формат
                self.status = TaskStatus(self.status)
        
        # Конвертируем priority в enum 
        if self.priority is None:
            self.priority = TaskPriority.NORMAL
        elif isinstance(self.priority, str):
            if self.priority.startswith('TaskPriority.'):
                # Извлекаем значение из строки "TaskPriority.NORMAL" -> "NORMAL"
                priority_name = self.priority.split('.')[-1]
                self.priority = TaskPriority[priority_name]
            else:
                # Если это уже правильный формат
                self.priority = TaskPriority[self.priority]


class TaskQueue:
    """
    Асинхронная система очередей задач на Redis.
    
    Особенности:
    - Приоритетные очереди
    - Отслеживание прогресса
    - Retry механизм
    - Мониторинг производительности
    """
    
    def __init__(self, redis_url: str = None, queue_prefix: str = "legalrag"):
        if redis_url is None:
            # Получаем URL из переменных окружения
            redis_url = os.getenv('REDIS_URL')
            if not redis_url:
                # Конструируем URL из отдельных переменных
                redis_host = os.getenv('REDIS_HOST', 'localhost')
                redis_port = os.getenv('REDIS_PORT', '6379') 
                redis_db = os.getenv('REDIS_DB', '0')
                redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
        self.redis_url = redis_url
        self.queue_prefix = queue_prefix
        self.redis_client: Optional[redis.Redis] = None
        
        # Ключи Redis
        self.queue_key = f"{queue_prefix}:queue"
        self.processing_key = f"{queue_prefix}:processing"
        self.tasks_key = f"{queue_prefix}:tasks"
        self.results_key = f"{queue_prefix}:results"
        self.stats_key = f"{queue_prefix}:stats"
        
        # Обработчики задач
        self.handlers: Dict[str, Callable] = {}
        
        logger.info(f" TaskQueue initialized with prefix: {queue_prefix}")
    
    async def connect(self):
        """Подключение к Redis."""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            logger.info(" Connected to Redis for TaskQueue")
        except Exception as e:
            logger.error(f" Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Отключение от Redis."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info(" Disconnected from Redis")
    
    async def add_task(
        self, 
        task_type: str, 
        data: Dict[str, Any], 
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3
    ) -> str:
        """
        Добавление задачи в очередь.
        
        Args:
            task_type: Тип задачи (например, "document_processing")
            data: Данные для обработки
            priority: Приоритет задачи
            max_retries: Максимальное количество попыток
            
        Returns:
            str: ID созданной задачи
        """
        task_id = str(uuid.uuid4())
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            data=data,
            priority=priority,
            max_retries=max_retries
        )
        
        # Сохраняем задачу
        await self.redis_client.hset(
            self.tasks_key, 
            task_id, 
            json.dumps(asdict(task), default=str)
        )
        
        # Добавляем в очередь с приоритетом (чем больше число, тем выше приоритет)
        priority_value = priority.value if hasattr(priority, 'value') else int(priority)
        await self.redis_client.zadd(
            self.queue_key, 
            {task_id: priority_value}
        )
        
        # Обновляем статистику
        await self._update_stats("tasks_created", 1)
        
        logger.info(f" Task {task_id} ({task_type}) added to queue with priority {priority.name}")
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Получение статуса задачи."""
        task_data = await self.redis_client.hget(self.tasks_key, task_id)
        if not task_data:
            return None
        
        task_dict = json.loads(task_data)
        
        # Конвертируем enum строки в правильные значения для совместимости
        if 'status' in task_dict and isinstance(task_dict['status'], str):
            if task_dict['status'].startswith('TaskStatus.'):
                # Извлекаем значение из строки "TaskStatus.PENDING" -> "pending"
                status_name = task_dict['status'].split('.')[-1].lower()
                task_dict['status'] = status_name
        
        # Проверяем есть ли результат
        result = await self.redis_client.hget(self.results_key, task_id)
        if result:
            task_dict["result"] = json.loads(result)
        
        return task_dict
    
    async def cancel_task(self, task_id: str) -> bool:
        """Отмена задачи."""
        # Удаляем из очереди
        removed_from_queue = await self.redis_client.zrem(self.queue_key, task_id)
        
        # Обновляем статус, если задача была в очереди
        if removed_from_queue:
            await self._update_task_status(task_id, TaskStatus.CANCELLED)
            logger.info(f" Task {task_id} cancelled")
            return True
        
        # Проверяем, не обрабатывается ли задача сейчас
        processing = await self.redis_client.sismember(self.processing_key, task_id)
        if processing:
            # Помечаем как отмененную, worker должен проверять этот статус
            await self._update_task_status(task_id, TaskStatus.CANCELLED)
            logger.info(f" Task {task_id} marked for cancellation")
            return True
        
        return False
    
    async def get_next_task(self, worker_id: str) -> Optional[Task]:
        """
        Получение следующей задачи для обработки.
        Используется worker'ами.
        """
        # Получаем задачу с наивысшим приоритетом
        result = await self.redis_client.zpopmax(self.queue_key)
        if not result:
            return None
        
        task_id, priority = result[0]
        
        # Добавляем в список обрабатываемых
        await self.redis_client.sadd(self.processing_key, task_id)
        
        # Получаем данные задачи
        task_data = await self.redis_client.hget(self.tasks_key, task_id)
        if not task_data:
            # Задача была удалена, убираем из processing
            await self.redis_client.srem(self.processing_key, task_id)
            return None
        
        task_dict = json.loads(task_data)
        
        # Task.__post_init__ теперь обрабатывает enum десериализацию
        task = Task(**task_dict)
        
        # Обновляем статус
        task.status = TaskStatus.PROCESSING
        task.started_at = time.time()
        task.worker_id = worker_id
        
        await self._save_task(task)
        
        logger.info(f" Task {task_id} assigned to worker {worker_id}")
        return task
    
    async def complete_task(self, task_id: str, result: Dict[str, Any]):
        """Завершение задачи с результатом."""
        await self._update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        await self.redis_client.srem(self.processing_key, task_id)
        
        # Сохраняем результат отдельно для быстрого доступа
        await self.redis_client.hset(
            self.results_key, 
            task_id, 
            json.dumps(result, default=str)
        )
        
        # Обновляем статистику
        await self._update_stats("tasks_completed", 1)
        
        logger.info(f" Task {task_id} completed")
    
    async def fail_task(self, task_id: str, error_message: str):
        """Помечание задачи как неудачной."""
        task_data = await self.redis_client.hget(self.tasks_key, task_id)
        if not task_data:
            return
        
        task_dict = json.loads(task_data)
        
        # Task.__post_init__ теперь обрабатывает enum десериализацию
        task = Task(**task_dict)
        
        task.retry_count += 1
        task.error_message = error_message
        
        if task.retry_count >= task.max_retries:
            # Окончательная неудача
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()
            await self.redis_client.srem(self.processing_key, task_id)
            await self._update_stats("tasks_failed", 1)
            logger.error(f" Task {task_id} failed permanently: {error_message}")
        else:
            # Возвращаем в очередь для повторной попытки
            task.status = TaskStatus.PENDING
            priority_value = task.priority.value if hasattr(task.priority, 'value') else int(task.priority)
            await self.redis_client.zadd(
                self.queue_key, 
                {task_id: priority_value}
            )
            await self.redis_client.srem(self.processing_key, task_id)
            logger.warning(f" Task {task_id} failed, retry {task.retry_count}/{task.max_retries}: {error_message}")
        
        await self._save_task(task)
    
    async def update_progress(self, task_id: str, progress: int, message: str = None):
        """Обновление прогресса задачи."""
        task_data = await self.redis_client.hget(self.tasks_key, task_id)
        if not task_data:
            return
        
        task_dict = json.loads(task_data)
        task_dict["progress"] = max(0, min(100, progress))
        
        if message:
            if "progress_messages" not in task_dict:
                task_dict["progress_messages"] = []
            task_dict["progress_messages"].append({
                "timestamp": time.time(),
                "message": message
            })
        
        await self.redis_client.hset(
            self.tasks_key, 
            task_id, 
            json.dumps(task_dict, default=str)
        )
        
        logger.debug(f" Task {task_id} progress: {progress}%")
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Получение статистики очереди."""
        stats = {
            "queue_size": await self.redis_client.zcard(self.queue_key),
            "processing_count": await self.redis_client.scard(self.processing_key),
            "total_tasks": await self.redis_client.hlen(self.tasks_key),
        }
        
        # Получаем дополнительную статистику
        stats_data = await self.redis_client.hgetall(self.stats_key)
        for key, value in stats_data.items():
            try:
                stats[key] = int(value)
            except ValueError:
                stats[key] = value
        
        return stats
    
    async def cleanup_old_tasks(self, older_than_hours: int = 24):
        """Очистка старых завершенных задач."""
        cutoff_time = time.time() - (older_than_hours * 3600)
        
        # Получаем все задачи
        all_tasks = await self.redis_client.hgetall(self.tasks_key)
        
        cleaned_count = 0
        for task_id, task_data in all_tasks.items():
            task_dict = json.loads(task_data)
            
            # Удаляем старые завершенные или неудачные задачи
            if (task_dict.get("completed_at") and 
                task_dict["completed_at"] < cutoff_time and 
                task_dict["status"] in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]):
                
                await self.redis_client.hdel(self.tasks_key, task_id)
                await self.redis_client.hdel(self.results_key, task_id)
                cleaned_count += 1
        
        logger.info(f" Cleaned up {cleaned_count} old tasks")
        return cleaned_count
    
    # Внутренние методы
    
    async def _save_task(self, task: Task):
        """Сохранение задачи в Redis."""
        await self.redis_client.hset(
            self.tasks_key, 
            task.task_id, 
            json.dumps(asdict(task), default=str)
        )
    
    async def _update_task_status(self, task_id: str, status: TaskStatus, result: Dict[str, Any] = None):
        """Обновление статуса задачи."""
        task_data = await self.redis_client.hget(self.tasks_key, task_id)
        if not task_data:
            return
        
        task_dict = json.loads(task_data)
        # Безопасное обновление статуса - проверяем тип
        if hasattr(status, 'value'):
            task_dict["status"] = status.value
        else:
            task_dict["status"] = status
        
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            task_dict["completed_at"] = time.time()
        
        if result:
            task_dict["result"] = result
        
        await self.redis_client.hset(
            self.tasks_key, 
            task_id, 
            json.dumps(task_dict, default=str)
        )
    
    async def _update_stats(self, key: str, increment: int = 1):
        """Обновление статистики."""
        await self.redis_client.hincrby(self.stats_key, key, increment)
    
    def register_handler(self, task_type: str, handler: Callable):
        """Регистрация обработчика для типа задач."""
        self.handlers[task_type] = handler
        logger.info(f" Handler registered for task type: {task_type}")
    
    async def process_tasks(self, worker_id: str = None):
        """
        Основной цикл обработки задач.
        Используется worker'ами.
        """
        if not worker_id:
            worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        
        logger.info(f" Worker {worker_id} started processing tasks")
        
        while True:
            try:
                # Получаем следующую задачу
                task = await self.get_next_task(worker_id)
                
                if not task:
                    # Нет задач, ждем
                    await asyncio.sleep(1)
                    continue
                
                logger.info(f" Processing task {task.task_id} ({task.task_type})")
                # Проверяем, не отменена ли задача
                current_status = await self.get_task_status(task.task_id)
                print(f" DEBUG: Got current_status: {current_status}")
                if current_status and current_status["status"] == TaskStatus.CANCELLED.value:
                    logger.info(f" Task {task.task_id} was cancelled, skipping")
                    await self.redis_client.srem(self.processing_key, task.task_id)
                    continue
                
                # Ищем обработчик
                handler = self.handlers.get(task.task_type)
                if not handler:
                    await self.fail_task(task.task_id, f"No handler for task type: {task.task_type}")
                    continue
                
                # Обрабатываем задачу
                try:
                    logger.info(f" Processing task {task.task_id} ({task.task_type})")
                    result = await handler(task)
                    await self.complete_task(task.task_id, result)
                    
                except Exception as e:
                    logger.error(f" Task {task.task_id} failed: {e}")
                    await self.fail_task(task.task_id, str(e))
            
            except Exception as e:
                logger.error(f" Worker {worker_id} error: {e}")
                await asyncio.sleep(5)


# Глобальный экземпляр очереди задач
task_queue = TaskQueue()


async def init_task_queue():
    """Инициализация глобальной очереди задач."""
    await task_queue.connect()


async def get_task_queue():
    """Получение инициализированного экземпляра Task Queue."""
    if task_queue.redis_client is None:
        await task_queue.connect()
    return task_queue


async def shutdown_task_queue():
    """Завершение работы очереди задач."""
    await task_queue.disconnect()