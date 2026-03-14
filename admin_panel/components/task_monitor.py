#!/usr/bin/env python3
"""
Task Monitor Component для Admin Panel
Компонент для мониторинга очереди задач обработки документов
"""

import streamlit as st
import requests
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


class TaskMonitorComponent:
    """Компонент для мониторинга задач в очереди"""
    
    def __init__(self, api_gateway_url: str = None):
        # Используем переменную окружения или внутренний Docker URL
        self.api_gateway_url = api_gateway_url or os.getenv('API_GATEWAY_URL', 'http://legalrag_microservices:8080')
        
    def render_task_monitor(self):
        """Основной интерфейс мониторинга задач"""
        
        st.header(" Мониторинг задач обработки")
        
        # Автообновление
        col1, col2, col3, col4 = st.columns([1.5, 1, 1, 1.5])
        with col1:
            auto_refresh = st.checkbox(" Автообновление (5с)", value=True)
        with col2:
            if st.button(" Обновить"):
                # Очищаем кэш и перезагружаем
                st.cache_data.clear()
                st.rerun()
        with col3:
            if st.button(" Отладка"):
                st.session_state['debug_mode'] = not st.session_state.get('debug_mode', False)
                st.rerun()
        with col4:
            st.caption(f" {self.api_gateway_url}")

        if auto_refresh:
            # Рабочее автообновление через JavaScript и st.rerun()
            st.markdown("""
            <script>
            setTimeout(function(){
                // Проверяем, есть ли активные задачи для обновления
                var hasActiveTasks = document.querySelector('[data-testid="stMarkdown"]');
                if (hasActiveTasks && hasActiveTasks.innerText.includes('Обрабатывается')) {
                    window.location.reload();
                }
            }, 5000);
            </script>
            """, unsafe_allow_html=True)

            # Показываем статус автообновления
            st.caption(" Автообновление каждые 5 секунд (только при наличии активных задач)")
        
        # Статистика очереди
        self._render_queue_stats()
        
        st.markdown("---")
        
        # Активные задачи текущего пользователя
        self._render_user_tasks()
        
        st.markdown("---")
        
        # Общий статус очереди (для админов)
        if st.session_state.get('username') == 'admin':
            self._render_admin_queue_view()
    
    def _render_queue_stats(self):
        """Отображение общей статистики очереди"""

        try:
            stats = self._get_queue_stats()
            if stats:
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric(" Ожидают", stats.get('queue_size', 0))
                with col2:
                    st.metric(" Обрабатываются", stats.get('processing_count', 0))
                with col3:
                    completed_count = stats.get('total_tasks', 0) - stats.get('tasks_failed', 0) - stats.get('queue_size', 0) - stats.get('processing_count', 0)
                    st.metric(" Завершено", max(0, completed_count))
                with col4:
                    st.metric(" Ошибки", stats.get('tasks_failed', 0))
                with col5:
                    st.metric(" Всего", stats.get('total_tasks', 0))
        except Exception as e:
            st.error(f" Ошибка получения статистики: {e}")
    
    def _render_user_tasks(self):
        """Отображение задач текущего пользователя"""

        st.subheader(" Ваши задачи обработки")

        # Получаем задачи из session state и localStorage
        processing_tasks = self._get_user_tasks()

        # Для админа показываем также все задачи из очереди
        if st.session_state.get('username') == 'admin':
            all_queue_tasks = self._get_all_queue_tasks()
            if all_queue_tasks:
                st.subheader(" Все задачи в системе (админ)")
                for task_id, task_info in list(all_queue_tasks.items())[:20]: # Показываем последние 20
                    self._render_single_task(task_info.get('original_filename', task_id[:8]), task_info)
                st.markdown("---")

        if not processing_tasks:
            if st.session_state.get('username') != 'admin':
                st.info(" У вас нет активных задач обработки")
            return
        
        # Обновляем статусы всех задач
        updated_tasks = {}
        tasks_to_display = []
        
        for file_name, task_info in processing_tasks.items():
            task_id = task_info.get('task_id')
            if task_id:
                # Получаем актуальный статус задачи
                # Приоритет: Task Queue (authoritative) -> API -> кэш
                current_status = self._get_task_status_from_redis(task_id)

                # Если Redis недоступен, пробуем через API
                if not current_status:
                    current_status = self._get_task_status(task_id)

                if current_status:
                    # Обновляем данные задачи
                    task_info.update(current_status)
                    updated_tasks[file_name] = task_info
                    tasks_to_display.append((file_name, task_info))

                    # Если статус изменился, обновляем пользовательский кэш в Redis
                    if (
                        current_status.get('status') != processing_tasks.get(file_name, {}).get('status') or
                        current_status.get('progress') != processing_tasks.get(file_name, {}).get('progress')
                    ):
                        self._update_user_task_in_redis(file_name, task_info)
                else:
                    # Если не удалось получить статус, показываем задачу как есть
                    updated_tasks[file_name] = task_info
                    tasks_to_display.append((file_name, task_info))
        
        # Обновляем session state и сохраняем в Redis
        st.session_state.processing_tasks = updated_tasks
        self._save_tasks_to_redis(updated_tasks)
        
        # Отладочная информация
        if st.session_state.get('debug_mode', False):
            with st.expander(" Отладочная информация"):
                st.write(f"**Session tasks:** {len(st.session_state.get('processing_tasks', {}))}")
                st.write(f"**Updated tasks:** {len(updated_tasks)}")
                st.write(f"**Tasks to display:** {len(tasks_to_display)}")
                if tasks_to_display:
                    st.json({name: {
                        'task_id': info.get('task_id', 'N/A')[:8] + '...',
                        'status': info.get('status', 'unknown'),
                        'progress': info.get('progress', 0)
                    } for name, info in tasks_to_display})

        # Отображаем задачи
        for file_name, task_info in tasks_to_display:
            self._render_single_task(file_name, task_info)
    
    def _render_single_task(self, file_name: str, task_info: Dict[str, Any]):
        """Отображение одной задачи"""
        
        status = task_info.get('status', 'pending')
        document_type = task_info.get('document_type', 'Неизвестно')
        created_at = task_info.get('created_at', time.time())
        task_id = task_info.get('task_id', 'Неизвестно')
        
        # Выбираем иконку и цвет на основе статуса
        if status == 'pending':
            status_icon = ""
            status_color = "orange"
            status_text = "Ожидает обработки"
        elif status == 'processing':
            status_icon = ""
            status_color = "blue"
            status_text = "Обрабатывается"
        elif status == 'completed':
            status_icon = ""
            status_color = "green"
            status_text = "Завершено"
        elif status == 'failed':
            status_icon = ""
            status_color = "red"
            status_text = "Ошибка"
        else:
            status_icon = ""
            status_color = "gray"
            status_text = "Неизвестно"
        
        # Создаем карточку задачи
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            
            with col1:
                st.write(f" **{file_name}**")
                st.caption(f"Тип: {document_type}")
            
            with col2:
                st.write(f"{status_icon} {status_text}")

                # Реальный прогресс-бар для всех задач
                progress = task_info.get('progress', 0)
                progress_messages = task_info.get('progress_messages', [])

                # Получаем последнее сообщение о прогрессе
                latest_message = ""
                if progress_messages and isinstance(progress_messages, list) and len(progress_messages) > 0:
                    latest_message = progress_messages[-1].get('message', '') if isinstance(progress_messages[-1], dict) else str(progress_messages[-1])

                if status == 'processing':
                    if progress > 0:
                        # Используем реальный прогресс из API
                        st.progress(progress / 100.0)
                        st.caption(f"{progress}% завершено")
                        if latest_message:
                            st.caption(f" {latest_message}")
                    else:
                        # Показываем индикатор обработки если нет конкретного прогресса
                        progress_value = self._estimate_processing_progress(created_at, document_type)
                        st.progress(progress_value)
                        st.caption(f"~{int(progress_value*100)}% завершено")
                        if latest_message:
                            st.caption(f" {latest_message}")
                elif status == 'completed':
                    st.progress(1.0)
                    st.caption("100% завершено")
                    if latest_message:
                        st.caption(f" {latest_message}")
                elif status == 'failed':
                    st.progress(0.0)
                    error_message = task_info.get('error_message', '')
                    if error_message:
                        st.caption(f" {error_message}")
                    elif latest_message:
                        st.caption(f" {latest_message}")
                elif status == 'pending':
                    # Для pending задач показываем позицию в очереди
                    queue_position = self._get_queue_position(task_id)
                    if queue_position:
                        st.caption(f" Позиция в очереди: #{queue_position}")
            
            with col3:
                elapsed_time = time.time() - created_at
                if elapsed_time < 60:
                    time_str = f"{int(elapsed_time)}с назад"
                elif elapsed_time < 3600:
                    time_str = f"{int(elapsed_time/60)}м назад"
                else:
                    time_str = f"{int(elapsed_time/3600)}ч назад"
                st.caption(f" {time_str}")
                st.caption(f"ID: {task_id[:8]}...")
            
            with col4:
                if status in ['completed', 'failed']:
                    if st.button("", key=f"remove_{task_id}", help="Убрать из списка"):
                        self._remove_task_from_session(file_name)
                        st.rerun()
        
        st.markdown("---")
    
    
    def _estimate_processing_progress(self, created_at: float, document_type: str = "") -> float:
        """Оценка прогресса обработки документа"""
        elapsed = time.time() - created_at

        # Разные временные рамки для разных типов документов
        if "презентация" in document_type.lower():
            # Презентации: 10-20 минут
            total_time = 1200 # 20 минут
        else:
            # Обычные документы: 2-5 минут
            total_time = 300 # 5 минут

        # Логарифмический прогресс
        if elapsed < total_time * 0.1: # первые 10%
            return min(0.3, elapsed / (total_time * 0.1) * 0.3)
        elif elapsed < total_time * 0.5: # до 50%
            return 0.3 + min(0.4, (elapsed - total_time * 0.1) / (total_time * 0.4) * 0.4)
        elif elapsed < total_time: # до полного времени
            return 0.7 + min(0.25, (elapsed - total_time * 0.5) / (total_time * 0.5) * 0.25)
        else: # превышено время
            return 0.95
    
    def _get_queue_stats(self) -> Optional[Dict[str, Any]]:
        """Получение статистики очереди"""
        try:
            # Убираем проверку auth_token для внутренних запросов
            headers = {}
            if hasattr(st.session_state, 'auth_token'):
                headers['Authorization'] = f'Bearer {st.session_state.auth_token}'

            response = requests.get(
                f"{self.api_gateway_url}/api/tasks/queue/stats",
                headers=headers,
                timeout=30 # Увеличиваем таймаут до 30 секунд
            )

            if response.status_code == 200:
                return response.json().get('stats', {})
            else:
                # Показываем отладочную информацию только админам
                if st.session_state.get('username') == 'admin':
                    st.error(f" Debug: API response status: {response.status_code}, text: {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            if st.session_state.get('username') == 'admin':
                st.error(f" Debug: Request exception in _get_queue_stats: {e}")
            return None
        except Exception as e:
            if st.session_state.get('username') == 'admin':
                st.error(f" Debug: Exception in _get_queue_stats: {e}")
            return None
    
    def _get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Получение статуса конкретной задачи"""
        try:
            # Убираем проверку auth_token для внутренних запросов
            headers = {}
            if hasattr(st.session_state, 'auth_token'):
                headers['Authorization'] = f'Bearer {st.session_state.auth_token}'

            response = requests.get(
                f"{self.api_gateway_url}/api/tasks/{task_id}/status",
                headers=headers,
                timeout=30 # Увеличиваем таймаут до 30 секунд
            )

            if response.status_code == 200:
                task_data = response.json()
                # Исправляем структуру ответа - данные могут быть на верхнем уровне
                if 'task_id' in task_data:
                    return task_data
                else:
                    return task_data.get('task', {})
            elif response.status_code == 404:
                # Задача не найдена - это нормально для завершенных задач
                return None
            else:
                # Показываем отладочную информацию только админам
                if st.session_state.get('username') == 'admin':
                    st.error(f" Debug: Task status API error: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            if st.session_state.get('username') == 'admin':
                st.error(f" Debug: Request exception in _get_task_status: {e}")
            return None
        except Exception as e:
            if st.session_state.get('username') == 'admin':
                st.error(f" Debug: Exception in _get_task_status: {e}")
            return None
    
    def _cleanup_old_tasks(self, hours: int = 24) -> Optional[Dict[str, Any]]:
        """Очистка старых задач"""
        try:
            if not hasattr(st.session_state, 'auth_token'):
                return None
            
            headers = {
                'Authorization': f'Bearer {st.session_state.auth_token}'
            }
            
            response = requests.post(
                f"{self.api_gateway_url}/api/tasks/cleanup?hours={hours}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"API ошибка очистки: {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"Исключение при очистке: {e}")
        return None
    
    def _remove_task_from_session(self, file_name: str):
        """Удаление задачи из session state и Redis"""
        if 'processing_tasks' in st.session_state:
            st.session_state.processing_tasks.pop(file_name, None)
            # Сохраняем обновленный список в Redis
            self._save_tasks_to_redis(st.session_state.processing_tasks)
    
    def _get_user_tasks(self) -> Dict[str, Any]:
        """Получение задач пользователя с persistent storage"""

        # Сначала пробуем session state
        session_tasks = st.session_state.get('processing_tasks', {})

        # Если session state пуст, пробуем восстановить из Redis
        if not session_tasks:
            try:
                restored_tasks = self._restore_tasks_from_redis()
                if restored_tasks:
                    st.session_state.processing_tasks = restored_tasks
                    session_tasks = restored_tasks
            except Exception as e:
                if st.session_state.get('username') == 'admin':
                    st.error(f" Debug: Error restoring tasks from Redis: {e}")

        return session_tasks

    def _get_all_queue_tasks(self) -> Dict[str, Any]:
        """Получение всех задач из очереди через детальную статистику"""
        try:
            # Пока используем простой подход - возвращаем пустой словарь
            # В будущем можно добавить API эндпоинт для получения всех задач
            return {}
        except Exception:
            pass
        return {}

    def _get_queue_position(self, task_id: str) -> Optional[int]:
        """Получение позиции в очереди"""
        try:
            # Пока это заглушка, можно добавить API эндпоинт в будущем
            return None
        except Exception:
            return None

    def _show_detailed_stats(self):
        """Показать детальную статистику"""
        stats = self._get_queue_stats()
        if stats:
            st.json(stats)
        else:
            st.error(" Не удалось получить детальную статистику")

    def _restore_tasks_from_redis(self) -> Dict[str, Any]:
        """Восстановление задач из Redis по user_id"""
        try:
            import redis
            import json
            import os

            # Подключаемся к Redis
            redis_host = os.getenv('REDIS_HOST', 'legalrag_redis')
            redis_port = int(os.getenv('REDIS_PORT', 6379))

            r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

            # Ключ для сохранения задач пользователя
            user_id = st.session_state.get('username', 'anonymous')
            redis_key = f"legalrag:user_tasks:{user_id}"

            # Получаем сохраненные задачи
            tasks_data = r.get(redis_key)
            if tasks_data:
                return json.loads(tasks_data)

        except Exception as e:
            # Не логируем ошибки подключения - это нормально
            pass

        return {}

    def _save_tasks_to_redis(self, tasks: Dict[str, Any]):
        """Сохранение задач в Redis по user_id"""
        try:
            import redis
            import json
            import os

            # Подключаемся к Redis
            redis_host = os.getenv('REDIS_HOST', 'legalrag_redis')
            redis_port = int(os.getenv('REDIS_PORT', 6379))

            r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

            # Ключ для сохранения задач пользователя
            user_id = st.session_state.get('username', 'anonymous')
            redis_key = f"legalrag:user_tasks:{user_id}"

            # Сохраняем с TTL 7 дней
            r.setex(redis_key, 604800, json.dumps(tasks)) # 7 дней = 604800 секунд

        except Exception:
            # Не логируем ошибки сохранения - это не критично
            pass

    def _get_task_status_from_redis(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Получение статуса задачи напрямую из Redis (fallback для API)"""
        try:
            import redis
            import json
            import os

            # Подключаемся к Redis
            redis_host = os.getenv('REDIS_HOST', 'legalrag_redis')
            redis_port = int(os.getenv('REDIS_PORT', 6379))

            r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

            # Ключ для Task Queue
            redis_key = f"legalrag:task:{task_id}"

            # Получаем данные задачи
            task_data = r.hgetall(redis_key)
            if task_data:
                # Преобразуем в нужный формат
                parsed_data = {}
                for key, value in task_data.items():
                    if key in ['created_at', 'started_at', 'completed_at']:
                        try:
                            parsed_data[key] = float(value) if value else None
                        except (ValueError, TypeError):
                            parsed_data[key] = None
                    elif key == 'progress':
                        try:
                            parsed_data[key] = int(float(value))
                        except (ValueError, TypeError):
                            parsed_data[key] = 0
                    elif key == 'progress_messages':
                        try:
                            parsed_data[key] = json.loads(value) if value else []
                        except (json.JSONDecodeError, TypeError):
                            parsed_data[key] = []
                    else:
                        parsed_data[key] = value

                # Преобразуем status
                if 'status' in parsed_data:
                    status = parsed_data['status']
                    if status.startswith('TaskStatus.'):
                        parsed_data['status'] = status.split('.')[-1].lower()

                return parsed_data

        except Exception as e:
            # Не логируем ошибки - это fallback метод
            pass

        return None

    def _update_user_task_in_redis(self, file_name: str, task_info: dict):
        """Обновление конкретной задачи в пользовательском кэше Redis"""
        try:
            import redis
            import json
            import os

            # Подключаемся к Redis
            redis_host = os.getenv('REDIS_HOST', 'legalrag_redis')
            redis_port = int(os.getenv('REDIS_PORT', 6379))

            r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

            # Ключ для сохранения задач пользователя
            user_id = st.session_state.get('username', 'anonymous')
            redis_key = f"legalrag:user_tasks:{user_id}"

            # Получаем текущие задачи
            current_tasks = {}
            existing_data = r.get(redis_key)
            if existing_data:
                current_tasks = json.loads(existing_data)

            # Обновляем конкретную задачу
            current_tasks[file_name] = task_info

            # Сохраняем обновленный список
            r.setex(redis_key, 604800, json.dumps(current_tasks)) # 7 дней

        except Exception:
            # Не логируем ошибки сохранения - это не критично
            pass

    async def _schedule_refresh(self):
        """Планирование обновления страницы"""
        await asyncio.sleep(5)
        st.rerun()