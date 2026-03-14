#!/usr/bin/env python3
"""
RAG Configuration Optimizer
Модуль для оптимизации параметров RAG системы и A/B тестирования.

Обеспечивает:
- Динамическую настройку параметров поиска
- A/B тестирование разных конфигураций
- Адаптивные пороги схожести
- Оптимизацию чанкования документов
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import json
import time
from datetime import datetime
from pathlib import Path

from core.settings import SETTINGS

logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """Конфигурация параметров RAG поиска."""
    
    # Параметры поиска
    max_chunks: int = 5
    similarity_threshold: float = 0.7
    max_chunk_length: int = 1000
    
    # Параметры чанкования 
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # Оптимизация
    enable_reranking: bool = True
    boost_exact_matches: bool = True
    metadata_weight: float = 0.1
    
    # Адаптивные настройки
    adaptive_threshold: bool = False
    min_similarity: float = 0.5
    max_similarity: float = 0.9
    
    # Кэширование
    enable_cache: bool = True
    cache_ttl: int = 300
    
    name: str = "default"
    description: str = "Базовая конфигурация"


@dataclass
class TestResult:
    """Результат тестирования конфигурации."""
    config_name: str
    query: str
    chunks_found: int
    relevance_score: float
    response_time: float
    answer_quality: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class RAGOptimizer:
    """
    Оптимизатор параметров RAG системы.
    
    Функциональность:
    - Создание и управление конфигурациями
    - A/B тестирование разных настроек
    - Автоматическая оптимизация параметров
    - Сбор и анализ метрик производительности
    """
    
    def __init__(self):
        self.configs = {}
        self.test_results = []
        self.config_file = Path("rag_configs.json")
        self.results_file = Path("rag_test_results.json")
        
        # Загрузка сохраненных конфигураций
        self._load_configs()
        
        # Создание базовых конфигураций если их нет
        if not self.configs:
            self._create_default_configs()
    
    def _load_configs(self):
        """Загрузка сохраненных конфигураций."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, config_data in data.items():
                        self.configs[name] = RAGConfig(**config_data)
                logger.info(f" Загружено {len(self.configs)} конфигураций")
        except Exception as e:
            logger.warning(f" Ошибка загрузки конфигураций: {e}")
    
    def _save_configs(self):
        """Сохранение конфигураций в файл."""
        try:
            data = {name: config.__dict__ for name, config in self.configs.items()}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(" Конфигурации сохранены")
        except Exception as e:
            logger.error(f" Ошибка сохранения конфигураций: {e}")
    
    def _create_default_configs(self):
        """Создание набора базовых конфигураций для тестирования."""
        
        # Консервативная конфигурация (текущие настройки)
        self.configs["conservative"] = RAGConfig(
            max_chunks=5,
            similarity_threshold=0.7,
            max_chunk_length=1000,
            chunk_size=1000,
            chunk_overlap=200,
            enable_reranking=False,
            boost_exact_matches=True,
            metadata_weight=0.1,
            name="conservative",
            description="Консервативные настройки - высокое качество, меньше результатов"
        )
        
        # Сбалансированная конфигурация 
        self.configs["balanced"] = RAGConfig(
            max_chunks=7,
            similarity_threshold=0.65,
            max_chunk_length=1200,
            chunk_size=1000,
            chunk_overlap=250,
            enable_reranking=True,
            boost_exact_matches=True,
            metadata_weight=0.15,
            name="balanced",
            description="Сбалансированные настройки - компромисс качества и полноты"
        )
        
        # Агрессивная конфигурация
        self.configs["aggressive"] = RAGConfig(
            max_chunks=10,
            similarity_threshold=0.6,
            max_chunk_length=1500,
            chunk_size=800,
            chunk_overlap=300,
            enable_reranking=True,
            boost_exact_matches=True,
            metadata_weight=0.2,
            name="aggressive", 
            description="Агрессивные настройки - максимальная полнота, больше результатов"
        )
        
        # Адаптивная конфигурация
        self.configs["adaptive"] = RAGConfig(
            max_chunks=8,
            similarity_threshold=0.65,
            max_chunk_length=1200,
            chunk_size=1000,
            chunk_overlap=200,
            enable_reranking=True,
            boost_exact_matches=True,
            metadata_weight=0.15,
            adaptive_threshold=True,
            min_similarity=0.5,
            max_similarity=0.8,
            name="adaptive",
            description="Адаптивные настройки - динамическая настройка порогов"
        )
        
        # OptimalRAG конфигурация
        self.configs["optimal"] = RAGConfig(
            max_chunks=15,
            similarity_threshold=0.6,
            max_chunk_length=1000,
            chunk_size=1000,
            chunk_overlap=200,
            enable_reranking=True,
            boost_exact_matches=True,
            metadata_weight=0.25,
            name="optimal",
            description="OptimalRAG настройки - для сложных запросов с фильтрами"
        )
        
        logger.info(" Созданы базовые конфигурации RAG")
        self._save_configs()
    
    def get_config(self, name: str) -> Optional[RAGConfig]:
        """Получение конфигурации по имени."""
        return self.configs.get(name)
    
    def add_config(self, config: RAGConfig):
        """Добавление новой конфигурации."""
        self.configs[config.name] = config
        self._save_configs()
        logger.info(f" Добавлена конфигурация: {config.name}")
    
    def list_configs(self) -> Dict[str, str]:
        """Список всех конфигураций с описаниями."""
        return {name: config.description for name, config in self.configs.items()}
    
    def optimize_threshold(self, query: str, expected_results: int = 5) -> float:
        """
        Оптимизация порога схожести для конкретного запроса.
        
        Алгоритм:
        1. Тестирование разных порогов от 0.5 до 0.9
        2. Поиск порога, дающего оптимальное количество результатов
        3. Возврат рекомендуемого порога
        """
        
        # Набор порогов для тестирования
        thresholds = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]
        best_threshold = 0.7
        best_score = float('inf')
        
        logger.info(f" Оптимизация порога для запроса: '{query[:50]}...'")
        
        for threshold in thresholds:
            try:
                # Здесь будет тестирование с реальной системой
                # Пока используем эмуляцию
                results_count = self._simulate_search(query, threshold)
                
                # Оценка качества (чем ближе к expected_results, тем лучше)
                score = abs(results_count - expected_results)
                
                logger.debug(f" Порог {threshold}: {results_count} результатов (оценка: {score})")
                
                if score < best_score:
                    best_score = score
                    best_threshold = threshold
                    
            except Exception as e:
                logger.warning(f" Ошибка тестирования порога {threshold}: {e}")
        
        logger.info(f" Оптимальный порог: {best_threshold}")
        return best_threshold
    
    def _simulate_search(self, query: str, threshold: float) -> int:
        """Симуляция поиска для тестирования порогов."""
        # Эмуляция поиска - в реальной системе здесь будет вызов поиска
        import random
        
        # Простая эмуляция: чем ниже порог, тем больше результатов
        base_results = 8
        threshold_factor = (1.0 - threshold) * 10
        noise = random.uniform(-2, 2)
        
        results = max(0, int(base_results + threshold_factor + noise))
        return min(results, 20) # Максимум 20 результатов
    
    async def run_ab_test(self, queries: List[str], config_names: List[str] = None) -> Dict[str, Any]:
        """
        Запуск A/B тестирования различных конфигураций.
        
        Args:
            queries: Список тестовых запросов
            config_names: Имена конфигураций для тестирования (None = все)
            
        Returns:
            Результаты тестирования с метриками и рекомендациями
        """
        
        if config_names is None:
            config_names = list(self.configs.keys())
        
        logger.info(f" Запуск A/B тестирования: {len(config_names)} конфигураций, {len(queries)} запросов")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "configs_tested": config_names,
            "queries_count": len(queries),
            "results": {},
            "summary": {}
        }
        
        for config_name in config_names:
            config = self.configs.get(config_name)
            if not config:
                logger.warning(f" Конфигурация '{config_name}' не найдена")
                continue
                
            logger.info(f" Тестирование конфигурации: {config_name}")
            
            config_results = {
                "config": config.__dict__,
                "query_results": [],
                "avg_chunks": 0,
                "avg_relevance": 0,
                "avg_response_time": 0,
                "success_rate": 0
            }
            
            total_chunks = 0
            total_relevance = 0
            total_time = 0
            successful_queries = 0
            
            for query in queries:
                try:
                    start_time = time.time()
                    
                    # Симуляция поиска с данной конфигурацией
                    chunks_found, relevance_score = await self._test_config_query(config, query)
                    
                    response_time = time.time() - start_time
                    
                    if chunks_found > 0:
                        successful_queries += 1
                        total_chunks += chunks_found
                        total_relevance += relevance_score
                    
                    total_time += response_time
                    
                    query_result = {
                        "query": query[:50] + "..." if len(query) > 50 else query,
                        "chunks_found": chunks_found,
                        "relevance_score": relevance_score,
                        "response_time": response_time
                    }
                    
                    config_results["query_results"].append(query_result)
                    
                    # Сохранение результата тестирования
                    test_result = TestResult(
                        config_name=config_name,
                        query=query,
                        chunks_found=chunks_found,
                        relevance_score=relevance_score,
                        response_time=response_time
                    )
                    self.test_results.append(test_result)
                    
                except Exception as e:
                    logger.error(f" Ошибка тестирования запроса '{query[:30]}...': {e}")
            
            # Вычисление средних значений
            if len(queries) > 0:
                config_results["avg_response_time"] = total_time / len(queries)
                config_results["success_rate"] = successful_queries / len(queries)
            
            if successful_queries > 0:
                config_results["avg_chunks"] = total_chunks / successful_queries
                config_results["avg_relevance"] = total_relevance / successful_queries
            
            results["results"][config_name] = config_results
        
        # Анализ результатов и создание сводки
        results["summary"] = self._analyze_ab_results(results["results"])
        
        # Сохранение результатов
        self._save_test_results(results)
        
        logger.info(" A/B тестирование завершено")
        return results
    
    async def _test_config_query(self, config: RAGConfig, query: str) -> Tuple[int, float]:
        """Тестирование конкретного запроса с заданной конфигурацией."""
        
        # Симуляция поиска - в реальной системе здесь будет реальный поиск
        import random
        
        # Эмуляция на основе параметров конфигурации
        base_chunks = min(config.max_chunks, 8)
        threshold_factor = (1.0 - config.similarity_threshold) * 5
        noise = random.uniform(-2, 2)
        
        chunks_found = max(0, int(base_chunks + threshold_factor + noise))
        chunks_found = min(chunks_found, config.max_chunks)
        
        # Эмуляция релевантности
        if chunks_found > 0:
            base_relevance = 0.7
            config_bonus = 0.1 if config.enable_reranking else 0
            relevance_score = min(1.0, base_relevance + config_bonus + random.uniform(-0.1, 0.1))
        else:
            relevance_score = 0.0
        
        return chunks_found, relevance_score
    
    def _analyze_ab_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Анализ результатов A/B тестирования."""
        
        summary = {
            "best_config": None,
            "best_score": 0,
            "rankings": {
                "by_relevance": [],
                "by_chunks": [],
                "by_speed": [],
                "by_success_rate": []
            },
            "recommendations": []
        }
        
        configs_data = []
        
        for config_name, data in results.items():
            score = (
                data.get("avg_relevance", 0) * 0.4 +
                min(data.get("success_rate", 0), 1.0) * 0.3 +
                min(data.get("avg_chunks", 0) / 10, 1.0) * 0.2 +
                max(0, 1.0 - data.get("avg_response_time", 1.0)) * 0.1
            )
            
            configs_data.append({
                "name": config_name,
                "score": score,
                "avg_relevance": data.get("avg_relevance", 0),
                "avg_chunks": data.get("avg_chunks", 0),
                "avg_response_time": data.get("avg_response_time", 0),
                "success_rate": data.get("success_rate", 0)
            })
        
        # Сортировка по общей оценке
        configs_data.sort(key=lambda x: x["score"], reverse=True)
        
        if configs_data:
            summary["best_config"] = configs_data[0]["name"]
            summary["best_score"] = configs_data[0]["score"]
        
        # Рейтинги по отдельным метрикам
        summary["rankings"]["by_relevance"] = sorted(configs_data, key=lambda x: x["avg_relevance"], reverse=True)
        summary["rankings"]["by_chunks"] = sorted(configs_data, key=lambda x: x["avg_chunks"], reverse=True)
        summary["rankings"]["by_speed"] = sorted(configs_data, key=lambda x: x["avg_response_time"])
        summary["rankings"]["by_success_rate"] = sorted(configs_data, key=lambda x: x["success_rate"], reverse=True)
        
        # Рекомендации
        if len(configs_data) > 0:
            best = configs_data[0]
            summary["recommendations"].append(f"Лучшая конфигурация: {best['name']} (оценка: {best['score']:.3f})")
            
            if best["success_rate"] < 0.8:
                summary["recommendations"].append("Рекомендуется снизить порог схожести для увеличения успешности")
            
            if best["avg_chunks"] < 3:
                summary["recommendations"].append("Рекомендуется увеличить max_chunks для более полных ответов")
            
            if best["avg_response_time"] > 2.0:
                summary["recommendations"].append("Рекомендуется оптимизировать производительность")
        
        return summary
    
    def _save_test_results(self, results: Dict[str, Any]):
        """Сохранение результатов тестирования."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rag_ab_test_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f" Результаты A/B тестирования сохранены в {filename}")
        except Exception as e:
            logger.error(f" Ошибка сохранения результатов: {e}")
    
    def generate_report(self) -> str:
        """Генерация отчета о конфигурациях и тестированиях."""
        
        report = [
            "# Отчет RAG Optimizer",
            f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Доступные конфигурации:",
            ""
        ]
        
        for name, config in self.configs.items():
            report.extend([
                f"### {name.upper()}",
                f"**Описание**: {config.description}",
                f"- Чанков: {config.max_chunks}",
                f"- Порог схожести: {config.similarity_threshold}",
                f"- Размер чанка: {config.chunk_size}",
                f"- Перекрытие: {config.chunk_overlap}",
                f"- Ранжирование: {'Да' if config.enable_reranking else 'Нет'}",
                ""
            ])
        
        if self.test_results:
            report.extend([
                "## История тестирований:",
                f"Всего тестов: {len(self.test_results)}",
                ""
            ])
            
            # Группировка по конфигурациям
            config_stats = {}
            for result in self.test_results:
                if result.config_name not in config_stats:
                    config_stats[result.config_name] = {
                        "count": 0,
                        "avg_chunks": 0,
                        "avg_relevance": 0,
                        "avg_time": 0
                    }
                
                stats = config_stats[result.config_name]
                stats["count"] += 1
                stats["avg_chunks"] = (stats["avg_chunks"] * (stats["count"] - 1) + result.chunks_found) / stats["count"]
                stats["avg_relevance"] = (stats["avg_relevance"] * (stats["count"] - 1) + result.relevance_score) / stats["count"]
                stats["avg_time"] = (stats["avg_time"] * (stats["count"] - 1) + result.response_time) / stats["count"]
            
            for config_name, stats in config_stats.items():
                report.extend([
                    f"**{config_name}**: {stats['count']} тестов",
                    f"- Среднее чанков: {stats['avg_chunks']:.1f}",
                    f"- Средняя релевантность: {stats['avg_relevance']:.3f}",
                    f"- Среднее время: {stats['avg_time']:.3f}с",
                    ""
                ])
        
        return "\n".join(report)


# Глобальный экземпляр оптимизатора
_optimizer = None

def get_rag_optimizer() -> RAGOptimizer:
    """Получение глобального экземпляра оптимизатора."""
    global _optimizer
    if _optimizer is None:
        _optimizer = RAGOptimizer()
    return _optimizer


if __name__ == "__main__":
    # Демонстрация работы оптимизатора
    optimizer = get_rag_optimizer()
    
    print(" RAG Optimizer - Доступные конфигурации:")
    for name, desc in optimizer.list_configs().items():
        print(f" {name}: {desc}")
    
    print(f"\n Отчет:\n{optimizer.generate_report()}")