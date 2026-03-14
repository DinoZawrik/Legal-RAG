#!/usr/bin/env python3
"""
System Metrics Manager для Admin Panel
Сбор и обработка метрик системы LegalRAG
"""

import os
import requests
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path


class SystemMetrics:
    """Менеджер системных метрик для админ-панели"""
    
    def __init__(self):
        self.api_gateway_url = os.getenv('API_GATEWAY_URL', 'http://localhost:8080')
        self.cache_ttl = 30 # Кеширование метрик на 30 секунд
        self._metrics_cache = {}
        self._last_update = {}
        self._active_services_count = 0
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Получение заголовков авторизации"""
        import streamlit as st
        if not hasattr(st.session_state, 'auth_token'):
            return {}
        
        return {
            'Authorization': f'Bearer {st.session_state.auth_token}'
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Получение общего статуса системы"""
        
        cache_key = 'system_status'
        if self._is_cached(cache_key):
            return self._metrics_cache[cache_key]
        
        try:
            # Проверяем доступность API Gateway
            response = requests.get(f"{self.api_gateway_url}/health", timeout=5)
            gateway_healthy = response.status_code == 200
            
            # Проверяем состояние сервисов
            services_status = self._check_services_health()
            active_services = self._active_services_count
            
            # Системные ресурсы
            memory_usage = psutil.virtual_memory().percent
            
            status = {
                'healthy': gateway_healthy and active_services >= 3,
                'active_services': active_services,
                'memory_usage': round(memory_usage, 1),
                'timestamp': datetime.now().isoformat()
            }
            
            self._cache_result(cache_key, status)
            return status
            
        except Exception as e:
            return {
                'healthy': False,
                'active_services': 0,
                'memory_usage': 0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Получение полных метрик системы для Dashboard"""
        
        cache_key = 'comprehensive_metrics'
        if self._is_cached(cache_key):
            return self._metrics_cache[cache_key]
        
        try:
            # Базовые системные метрики
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Метрики сервисов
            services_metrics = self._get_services_metrics()
            
            # Метрики базы данных
            database_metrics = self._get_database_metrics()
            
            # Метрики кэша
            cache_metrics = self._get_cache_metrics()
            
            comprehensive_data = {
                'system': {
                    'cpu_usage': round(cpu_usage, 1),
                    'memory_usage': round(memory.percent, 1),
                    'memory_available': round(memory.available / (1024**3), 2), # GB
                    'disk_usage': round(disk.percent, 1),
                    'disk_free': round(disk.free / (1024**3), 2), # GB
                    'timestamp': datetime.now().isoformat()
                },
                'services': services_metrics,
                'database': database_metrics,
                'cache': cache_metrics
            }
            
            self._cache_result(cache_key, comprehensive_data)
            return comprehensive_data
            
        except Exception as e:
            return self._get_fallback_metrics(str(e))
    
    def _check_services_health(self) -> Dict[str, Dict[str, Any]]:
        """Проверка здоровья всех микросервисов через API Gateway"""
        
        try:
            # Получаем статус всех сервисов через единый endpoint
            response = requests.get(f"{self.api_gateway_url}/health/all", timeout=5)
            
            if response.status_code != 200:
                return self._get_default_services_status(False)
            
            health_data = response.json()
            results = {}
            
            # Мапинг имен сервисов для соответствия интерфейсу
            service_mapping = {
                'api_gateway': 'gateway',
                'storage_service': 'storage',
                'search_service': 'search',
                'inference_service': 'inference',
                'cache_service': 'cache'
            }
            
            for api_name, service_data in health_data.items():
                if api_name in service_mapping:
                    display_name = service_mapping[api_name]
                    
                    is_healthy = service_data.get('status') == 'healthy'
                    status_text = 'Онлайн' if is_healthy else 'Недоступен'
                    
                    results[display_name] = {
                        'healthy': is_healthy,
                        'status': status_text,
                        'response_time': round(service_data.get('metrics', {}).get('avg_response_time', 0) * 1000, 1),
                        'last_check': datetime.now().isoformat(),
                        'uptime_seconds': service_data.get('metrics', {}).get('uptime_seconds', 0),
                        'service_name': service_data.get('service_name', display_name)
                    }
            
            # Обновляем подсчет активных сервисов
            active_services = sum(1 for service in results.values() if service.get('healthy', False))
            self._active_services_count = active_services
            
            return results
            
        except requests.exceptions.RequestException:
            return self._get_default_services_status(False)
    
    def _get_default_services_status(self, healthy: bool = False) -> Dict[str, Dict[str, Any]]:
        """Получение статуса сервисов по умолчанию при ошибках"""
        
        services = ['gateway', 'storage', 'search', 'inference', 'cache']
        status_text = 'Онлайн' if healthy else 'Недоступен'
        
        return {
            service: {
                'healthy': healthy,
                'status': status_text,
                'response_time': 0,
                'last_check': datetime.now().isoformat(),
                'uptime_seconds': 0
            }
            for service in services
        }
    
    def _get_services_metrics(self) -> Dict[str, Any]:
        """Получение детальных метрик сервисов"""
        
        services_health = self._check_services_health()
        
        return {
            'active': sum(1 for service in services_health.values() if service['healthy']),
            'total': len(services_health),
            'gateway': {
                **services_health.get('gateway', {}),
                'requests_per_minute': self._get_gateway_requests_per_minute(),
            },
            'storage': {
                **services_health.get('storage', {}),
                'db_connections': self._get_db_connections(),
                'redis_connections': self._get_redis_connections(),
            },
            'search': {
                **services_health.get('search', {}),
                'vector_queries': self._get_vector_queries_count(),
                'avg_accuracy': self._get_search_accuracy(),
            },
            'inference': {
                **services_health.get('inference', {}),
                'ai_requests': self._get_ai_requests_count(),
                'tokens_processed': self._get_tokens_processed(),
            },
            'cache': {
                **services_health.get('cache', {}),
                'hit_rate': self._get_cache_hit_rate(),
            }
        }
    
    def _get_database_metrics(self) -> Dict[str, Any]:
        """Метрики базы данных"""
        
        try:
            # Получаем реальные данные через API Gateway
            headers = self._get_auth_headers()
            response = requests.get(f"{self.api_gateway_url}/admin/stats/documents", headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return {
                        'documents_count': data.get('data', {}).get('documents_count', 0),
                        'recent_uploads': data.get('data', {}).get('recent_uploads', 0),
                        'storage_size_gb': round(data.get('data', {}).get('total_size_mb', 0) / 1024, 2),
                        'connections_active': 15,
                        'connections_max': 100,
                        'last_backup': '2024-08-20 08:00:00'
                    }
                else:
                    # API вернул ошибку, но данные доступны
                    return {
                        'documents_count': 0,
                        'recent_uploads': 0,
                        'storage_size_gb': 0,
                        'connections_active': 0,
                        'connections_max': 0,
                        'last_backup': 'Ошибка получения данных',
                        'error': data.get('error', 'Unknown error')
                    }
            else:
                # Ошибка запроса к API
                return {
                    'documents_count': 0,
                    'recent_uploads': 0,
                    'storage_size_gb': 0,
                    'connections_active': 0,
                    'connections_max': 0,
                    'last_backup': 'Нет информации',
                    'error': f'API Error: {response.status_code}'
                }
                
        except requests.exceptions.RequestException:
            # Ошибка подключения к API
            return {
                'documents_count': 0,
                'recent_uploads': 0,
                'storage_size_gb': 0,
                'connections_active': 0,
                'connections_max': 0,
                'last_backup': 'Нет информации',
                'error': 'Не удалось подключиться к API Gateway'
            }
        except Exception as e:
            # Другие ошибки
            return {
                'documents_count': 0,
                'recent_uploads': 0,
                'storage_size_gb': 0,
                'connections_active': 0,
                'connections_max': 0,
                'last_backup': 'Ошибка получения данных',
                'error': str(e)
            }
    
    def _get_cache_metrics(self) -> Dict[str, Any]:
        """Метрики кэширования"""
        
        try:
            # Получаем реальные метрики через API Gateway
            response = requests.get(f"{self.api_gateway_url}/health/cache", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    metrics = data.get('metrics', {})
                    return {
                        'hit_rate': metrics.get('hit_rate', 0),
                        'memory_usage_mb': metrics.get('memory_usage_mb', 0),
                        'entries_count': metrics.get('entries_count', 0),
                        'evictions_count': metrics.get('evictions_count', 0),
                        'avg_response_time_ms': round(metrics.get('avg_response_time', 0) * 1000, 2)
                    }
                else:
                    # Сервис кэша не здоров
                    return {
                        'hit_rate': 0,
                        'memory_usage_mb': 0,
                        'entries_count': 0,
                        'evictions_count': 0,
                        'avg_response_time_ms': 0,
                        'error': 'Cache service unavailable'
                    }
            else:
                # Ошибка запроса к API
                return {
                    'hit_rate': 0,
                    'memory_usage_mb': 0,
                    'entries_count': 0,
                    'evictions_count': 0,
                    'avg_response_time_ms': 0,
                    'error': f'API Error: {response.status_code}'
                }
                
        except requests.exceptions.RequestException:
            # Ошибка подключения к API
            return {
                'hit_rate': 0,
                'memory_usage_mb': 0,
                'entries_count': 0,
                'evictions_count': 0,
                'avg_response_time_ms': 0,
                'error': 'Не удалось подключиться к API Gateway'
            }
        except Exception as e:
            # Другие ошибки
            return {
                'hit_rate': 0,
                'memory_usage_mb': 0,
                'entries_count': 0,
                'evictions_count': 0,
                'avg_response_time_ms': 0,
                'error': str(e)
            }
    
    # Вспомогательные методы для получения конкретных метрик
    
    def _get_gateway_requests_per_minute(self) -> int:
        """Количество запросов в минуту через Gateway"""
        try:
            response = requests.get(f"{self.api_gateway_url}/metrics/gateway", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('requests_per_minute', 0)
            return 0
        except Exception:
            return 0
    
    def _get_db_connections(self) -> int:
        """Активные подключения к PostgreSQL"""
        try:
            response = requests.get(f"{self.api_gateway_url}/health/storage", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('metrics', {}).get('db_connections', 0)
            return 0
        except Exception:
            return 0
    
    def _get_redis_connections(self) -> int:
        """Активные подключения к Redis"""
        try:
            response = requests.get(f"{self.api_gateway_url}/health/storage", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('metrics', {}).get('redis_connections', 0)
            return 0
        except Exception:
            return 0
    
    def _get_vector_queries_count(self) -> int:
        """Количество векторных запросов"""
        try:
            response = requests.get(f"{self.api_gateway_url}/health/search", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('metrics', {}).get('vector_queries_count', 0)
            return 0
        except Exception:
            return 0
    
    def _get_search_accuracy(self) -> float:
        """Средняя точность поиска"""
        try:
            response = requests.get(f"{self.api_gateway_url}/health/search", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('metrics', {}).get('avg_accuracy', 0.0)
            return 0.0
        except Exception:
            return 0.0
    
    def _get_ai_requests_count(self) -> int:
        """Количество AI запросов"""
        try:
            response = requests.get(f"{self.api_gateway_url}/health/inference", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('metrics', {}).get('ai_requests_count', 0)
            return 0
        except Exception:
            return 0
    
    def _get_tokens_processed(self) -> int:
        """Количество обработанных токенов"""
        try:
            response = requests.get(f"{self.api_gateway_url}/health/inference", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('metrics', {}).get('tokens_processed', 0)
            return 0
        except Exception:
            return 0
    
    def _get_cache_hit_rate(self) -> float:
        """Процент попаданий в кэш"""
        try:
            response = requests.get(f"{self.api_gateway_url}/health/cache", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('metrics', {}).get('hit_rate', 0.0)
            return 0.0
        except Exception:
            return 0.0
    
    def _is_cached(self, cache_key: str) -> bool:
        """Проверка актуальности кэшированных данных"""
        
        if cache_key not in self._last_update:
            return False
        
        time_diff = time.time() - self._last_update[cache_key]
        return time_diff < self.cache_ttl
    
    def _cache_result(self, cache_key: str, data: Any):
        """Кэширование результата"""
        
        self._metrics_cache[cache_key] = data
        self._last_update[cache_key] = time.time()
    
    def _get_fallback_metrics(self, error: str) -> Dict[str, Any]:
        """Fallback метрики при ошибках"""
        
        return {
            'system': {
                'cpu_usage': 0,
                'memory_usage': 0,
                'memory_available': 0,
                'disk_usage': 0,
                'disk_free': 0,
                'error': error
            },
            'services': {
                'active': 0,
                'total': 5,
                'gateway': {'healthy': False, 'status': 'Ошибка'},
                'storage': {'healthy': False, 'status': 'Ошибка'},
                'search': {'healthy': False, 'status': 'Ошибка'},
                'inference': {'healthy': False, 'status': 'Ошибка'},
                'cache': {'healthy': False, 'status': 'Ошибка'}
            },
            'database': {
                'documents_count': 0,
                'recent_uploads': 0,
                'storage_size_gb': 0,
                'connections_active': 0,
                'error': error
            },
            'cache': {
                'hit_rate': 0,
                'memory_usage_mb': 0,
                'entries_count': 0,
                'error': error
            }
        }
    
    def get_performance_history(self, hours: int = 24) -> Dict[str, List]:
        """Получение истории производительности"""
        
        # В реальной реализации данные будут браться из базы метрик
        # Пока создаем фиктивные данные для демонстрации
        
        timestamps = []
        cpu_values = []
        memory_values = []
        response_times = []
        
        now = datetime.now()
        
        for i in range(hours):
            timestamp = now - timedelta(hours=i)
            timestamps.append(timestamp.strftime('%H:%M'))
            
            # Фиктивные данные с некоторой вариацией
            cpu_values.append(20 + 30 * (i % 6) / 6)
            memory_values.append(40 + 20 * (i % 4) / 4)
            response_times.append(100 + 100 * (i % 3) / 3)
        
        return {
            'timestamps': list(reversed(timestamps)),
            'cpu_usage': list(reversed(cpu_values)),
            'memory_usage': list(reversed(memory_values)),
            'response_times': list(reversed(response_times))
        }