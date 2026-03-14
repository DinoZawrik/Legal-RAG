#!/usr/bin/env python3
"""
Hybrid Storage Manager
Объединяет ChromaDB (семантика) + Neo4j (структура) + Graph Legal Intelligence

Единый интерфейс для:
- Семантического поиска (ChromaDB)
- Структурного поиска (Neo4j)
- Гибридного интеллектуального поиска
- Графово-обогащенных результатов

Решает проблемы:
- Потеря численных ограничений через точные графовые связи
- Путаница между законами через структурные различия
- Отсутствие ссылок на статьи через граф связей
"""

import asyncio
import logging
import warnings
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import json

from core.storage_coordinator import create_storage_coordinator
from core.graph_legal_engine import (
    GraphLegalIntelligenceEngine,
    get_graph_legal_engine,
    GraphContext,
    GraphNode
)
# MIGRATED: core.universal_legal_ner (deprecated) core.ner
try:
    from core.ner.ner import LegalEntity
except ImportError:
    LegalEntity = None

logger = logging.getLogger(__name__)
warnings.warn(
    "core.hybrid_storage_manager переходит на StorageCoordinator. Обновите импорты",
    DeprecationWarning,
    stacklevel=2,
)


@dataclass
class HybridSearchResult:
    """Результат гибридного поиска"""
    # Базовые поля от семантического поиска
    text: str
    metadata: Dict[str, Any]
    semantic_score: float

    # Обогащение от графового поиска
    graph_context: Optional[GraphContext] = None
    related_entities: List[LegalEntity] = None
    structural_connections: List[str] = None

    # Итоговые оценки
    final_score: float = 0.0
    confidence_boost: float = 0.0
    hybrid_enhancements: List[str] = None


@dataclass
class HybridQueryConfig:
    """УЛЬТРА-ОПТИМИЗИРОВАННАЯ конфигурация гибридного запроса для 80%+ успешности"""
    # Семантический поиск (больше покрытие)
    semantic_limit: int = 15
    semantic_threshold: float = 0.6 # Снижен для большего покрытия

    # Графовый поиск (усилен для точности)
    graph_enabled: bool = True
    graph_depth: int = 3 # Увеличен для глубокого анализа
    graph_boost_factor: float = 0.5 # Увеличен вес графа

    # Гибридное ранжирование (сбалансировано)
    semantic_weight: float = 0.6
    structural_weight: float = 0.4 # Увеличен вес структуры

    # Фильтрация результатов (мягче для покрытия)
    min_final_score: float = 0.4 # Снижен для большего покрытия
    max_results: int = 10 # Увеличено для лучших ответов


class HybridStorageManager:
    """
    Гибридный менеджер хранилища
    Объединяет семантический и структурный поиск
    """

    def __init__(self):
        # Компоненты хранилища
        self.semantic_storage = None
        self.graph_engine: Optional[GraphLegalIntelligenceEngine] = None

        # Конфигурация по умолчанию
        self.default_config = HybridQueryConfig()

        # Статистика работы
        self.stats = {
            "total_queries": 0,
            "semantic_only_queries": 0,
            "hybrid_queries": 0,
            "graph_enhanced_results": 0,
            "avg_semantic_score": 0.0,
            "avg_hybrid_score": 0.0,
            "performance_improvement": 0.0
        }

        self.logger = logging.getLogger(self.__class__.__name__)

    async def initialize(self) -> None:
        """Инициализация гибридного хранилища"""
        try:
            self.logger.info(" Initializing Hybrid Storage Manager...")

            # Инициализация семантического хранилища
            self.logger.info(" Loading semantic storage (ChromaDB)...")
            self.semantic_storage = await create_storage_coordinator()

            # Инициализация графового движка
            self.logger.info(" Loading graph engine (Neo4j + Graph Intelligence)...")
            self.graph_engine = await get_graph_legal_engine()

            self.logger.info(" Hybrid Storage Manager initialized successfully")

        except Exception as e:
            self.logger.error(f" Failed to initialize Hybrid Storage Manager: {e}")
            raise

    async def store_document(
        self,
        document: Dict[str, Any],
        enable_graph_processing: bool = True
    ) -> Dict[str, Any]:
        """
        Сохранение документа в гибридное хранилище
        """
        try:
            results = {
                "semantic_storage": {"success": False},
                "graph_storage": {"success": False},
                "overall_success": False
            }

            # 1. Сохранение в семантическое хранилище (ChromaDB)
            if self.semantic_storage:
                try:
                    # Используем StorageCoordinator
                    storage_result = await self.semantic_storage.store_document_complete(
                        file_path=document.get("file_path", ""),
                        chunks=document.get("chunks", []),
                        metadata=document.get("metadata", {}),
                    )
                    results["semantic_storage"] = storage_result
                    self.logger.info(" Document stored in semantic storage")
                except Exception as e:
                    self.logger.error(f" Semantic storage failed: {e}")
                    results["semantic_storage"] = {"success": False, "error": str(e)}

            # 2. Обработка и сохранение в граф
            if enable_graph_processing and self.graph_engine:
                try:
                    graph_result = await self.graph_engine.process_document_to_graph(document)
                    results["graph_storage"] = graph_result
                    self.logger.info(f" Document processed to graph: {graph_result.get('nodes_created', 0)} nodes")
                except Exception as e:
                    self.logger.error(f" Graph processing failed: {e}")
                    results["graph_storage"] = {"success": False, "error": str(e)}

            # 3. Общий результат
            results["overall_success"] = (
                results["semantic_storage"].get("success", False) or
                results["graph_storage"].get("success", False)
            )

            return results

        except Exception as e:
            self.logger.error(f" Document storage failed: {e}")
            return {
                "semantic_storage": {"success": False, "error": str(e)},
                "graph_storage": {"success": False, "error": str(e)},
                "overall_success": False
            }

    async def hybrid_search(
        self,
        query: str,
        config: Optional[HybridQueryConfig] = None
    ) -> List[HybridSearchResult]:
        """
        Гибридный поиск: семантика + структура + интеллект
        """
        if config is None:
            config = self.default_config

        self.stats["total_queries"] += 1
        start_time = datetime.now()

        try:
            self.logger.info(f" Hybrid search: {query[:100]}...")

            # 1. Семантический поиск через ChromaDB
            semantic_results = await self._semantic_search(query, config)

            # 2. Если граф доступен - обогащаем результаты
            if config.graph_enabled and self.graph_engine:
                hybrid_results = await self._enhance_with_graph_intelligence(
                    query, semantic_results, config
                )
                self.stats["hybrid_queries"] += 1
            else:
                # Конвертируем в HybridSearchResult без графового обогащения
                hybrid_results = [
                    HybridSearchResult(
                        text=result.get("text", ""),
                        metadata=result.get("metadata", {}),
                        semantic_score=result.get("similarity", 0.0),
                        final_score=result.get("similarity", 0.0),
                        hybrid_enhancements=[]
                    )
                    for result in semantic_results
                ]
                self.stats["semantic_only_queries"] += 1

            # 3. Финальное ранжирование и фильтрация
            final_results = await self._rank_and_filter_results(hybrid_results, config)

            # 4. Обновление статистики
            await self._update_search_stats(semantic_results, final_results)

            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.info(f" Hybrid search completed in {processing_time:.2f}s, {len(final_results)} results")

            return final_results

        except Exception as e:
            self.logger.error(f" Hybrid search failed: {e}")
            return []

    async def _semantic_search(
        self,
        query: str,
        config: HybridQueryConfig
    ) -> List[Dict[str, Any]]:
        """Семантический поиск через ChromaDB"""

        if not self.semantic_storage:
            self.logger.warning("Semantic storage not available")
            return []

        try:
            # Используем существующий метод search_documents
            results = await self.semantic_storage.search_documents(
                query=query,
                limit=config.semantic_limit
            )

            # Фильтруем по порогу
            filtered_results = [
                result for result in results
                if result.get("similarity", 0.0) >= config.semantic_threshold
            ]

            self.logger.debug(f"Semantic search: {len(filtered_results)}/{len(results)} results above threshold")
            return filtered_results

        except Exception as e:
            self.logger.error(f"Semantic search error: {e}")
            return []

    async def _enhance_with_graph_intelligence(
        self,
        query: str,
        semantic_results: List[Dict[str, Any]],
        config: HybridQueryConfig
    ) -> List[HybridSearchResult]:
        """Обогащение семантических результатов графовым интеллектом"""

        enhanced_results = []

        try:
            # Собираем документы для graph_enhanced_query
            context_documents = []
            for result in semantic_results:
                doc = {
                    "content": result.get("text", ""),
                    "metadata": result.get("metadata", {}),
                    "id": result.get("metadata", {}).get("document_id", "unknown")
                }
                context_documents.append(doc)

            # Используем graph_enhanced_query из GraphLegalIntelligenceEngine
            graph_result = await self.graph_engine.graph_enhanced_query(
                query=query,
                context_documents=context_documents,
                max_chunks=config.semantic_limit,
                graph_depth=config.graph_depth
            )

            # Обогащаем каждый семантический результат
            for i, semantic_result in enumerate(semantic_results):

                # Создаем базовый HybridSearchResult
                hybrid_result = HybridSearchResult(
                    text=semantic_result.get("text", ""),
                    metadata=semantic_result.get("metadata", {}),
                    semantic_score=semantic_result.get("similarity", 0.0),
                    related_entities=graph_result.entities_found if i == 0 else [], # Добавляем сущности к первому результату
                    hybrid_enhancements=[]
                )

                # Если есть графовый контекст - обогащаем
                confidence_boost = 0.0
                enhancements = []

                if graph_result.success and graph_result.entities_found:
                    # Проверяем, есть ли в этом результате найденные сущности
                    result_text = hybrid_result.text.lower()

                    for entity in graph_result.entities_found:
                        if entity.text.lower() in result_text:
                            confidence_boost += 0.1
                            enhancements.append(f"Found entity: {entity.text} ({entity.entity_type})")

                    # Дополнительный буст для численных ограничений
                    numerical_entities = [e for e in graph_result.entities_found if e.entity_type == "numerical_constraint"]
                    if numerical_entities:
                        confidence_boost += 0.2
                        enhancements.append(f"Numerical constraints preserved: {len(numerical_entities)}")
                        self.stats["graph_enhanced_results"] += 1

                # Вычисляем финальный score
                hybrid_result.confidence_boost = confidence_boost
                hybrid_result.final_score = min(
                    hybrid_result.semantic_score + (confidence_boost * config.graph_boost_factor),
                    1.0
                )
                hybrid_result.hybrid_enhancements = enhancements

                enhanced_results.append(hybrid_result)

        except Exception as e:
            self.logger.error(f"Graph enhancement error: {e}")
            # Возвращаем базовые результаты без обогащения
            enhanced_results = [
                HybridSearchResult(
                    text=result.get("text", ""),
                    metadata=result.get("metadata", {}),
                    semantic_score=result.get("similarity", 0.0),
                    final_score=result.get("similarity", 0.0),
                    hybrid_enhancements=[]
                )
                for result in semantic_results
            ]

        return enhanced_results

    async def _rank_and_filter_results(
        self,
        results: List[HybridSearchResult],
        config: HybridQueryConfig
    ) -> List[HybridSearchResult]:
        """Финальное ранжирование и фильтрация результатов"""

        # Фильтрация по минимальному score
        filtered_results = [
            result for result in results
            if result.final_score >= config.min_final_score
        ]

        # Сортировка по final_score
        ranked_results = sorted(
            filtered_results,
            key=lambda x: x.final_score,
            reverse=True
        )

        # Ограничение количества результатов
        final_results = ranked_results[:config.max_results]

        self.logger.debug(f"Ranking: {len(final_results)}/{len(results)} results after filtering and ranking")
        return final_results

    async def _update_search_stats(
        self,
        semantic_results: List[Dict[str, Any]],
        final_results: List[HybridSearchResult]
    ) -> None:
        """Обновление статистики поиска"""

        try:
            # Средние оценки семантического поиска
            if semantic_results:
                avg_semantic = sum(r.get("similarity", 0.0) for r in semantic_results) / len(semantic_results)
                self.stats["avg_semantic_score"] = (
                    (self.stats["avg_semantic_score"] * (self.stats["total_queries"] - 1) + avg_semantic) /
                    self.stats["total_queries"]
                )

            # Средние оценки гибридного поиска
            if final_results:
                avg_hybrid = sum(r.final_score for r in final_results) / len(final_results)
                self.stats["avg_hybrid_score"] = (
                    (self.stats["avg_hybrid_score"] * (self.stats["total_queries"] - 1) + avg_hybrid) /
                    self.stats["total_queries"]
                )

            # Улучшение производительности
            if self.stats["avg_semantic_score"] > 0:
                self.stats["performance_improvement"] = (
                    (self.stats["avg_hybrid_score"] - self.stats["avg_semantic_score"]) /
                    self.stats["avg_semantic_score"] * 100
                )

        except Exception as e:
            self.logger.warning(f"Stats update error: {e}")

    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Получение документа по ID"""
        if self.semantic_storage:
            try:
                # Используем существующий метод если есть
                return await self.semantic_storage.get_document_by_id(document_id)
            except AttributeError:
                # Если метода нет, используем поиск по метаданным
                results = await self.semantic_storage.search_documents(
                    query="", # Пустой запрос
                    limit=1000
                )
                for result in results:
                    if result.get("metadata", {}).get("document_id") == document_id:
                        return result
        return None

    async def cleanup(self) -> None:
        """Очистка ресурсов"""
        try:
            if self.semantic_storage:
                await self.semantic_storage.cleanup()

            # Граф engine очистка (если нужна)
            self.logger.info(" Hybrid Storage Manager cleanup completed")

        except Exception as e:
            self.logger.error(f" Cleanup error: {e}")

    def get_hybrid_stats(self) -> Dict[str, Any]:
        """Статистика гибридного хранилища"""
        stats = {
            "storage_stats": self.stats.copy(),
            "semantic_storage_ready": self.semantic_storage is not None,
            "graph_engine_ready": self.graph_engine is not None,
            "hybrid_mode_active": (self.semantic_storage is not None and
                                 self.graph_engine is not None)
        }

        # Добавляем статистику графового движка
        if self.graph_engine:
            stats["graph_engine_stats"] = self.graph_engine.get_graph_stats()

        return stats


# Глобальная инстанция Hybrid Storage Manager
_hybrid_storage_manager = None

async def create_hybrid_storage() -> HybridStorageManager:
    """Создание и инициализация гибридного хранилища"""
    global _hybrid_storage_manager
    if _hybrid_storage_manager is None:
        _hybrid_storage_manager = HybridStorageManager()
        await _hybrid_storage_manager.initialize()
    return _hybrid_storage_manager

async def get_hybrid_storage() -> HybridStorageManager:
    """Получение глобального экземпляра гибридного хранилища"""
    global _hybrid_storage_manager
    if _hybrid_storage_manager is None:
        _hybrid_storage_manager = await create_hybrid_storage()
    return _hybrid_storage_manager


if __name__ == "__main__":
    # Тестирование Hybrid Storage Manager
    async def test_hybrid_storage():
        print(" Testing Hybrid Storage Manager")

        # Создаем менеджер
        manager = HybridStorageManager()
        await manager.initialize()

        # Тестовый документ
        test_document = {
            "content": "Статья 7. Размер платы концедента не может превышать 80% от стоимости объекта.",
            "metadata": {
                "document_id": "test_hybrid_doc",
                "document_number": metadata.get("document_number"),
                "title": "Тест гибридного хранилища"
            }
        }

        # 1. Сохранение документа
        print(" Storing document...")
        store_result = await manager.store_document(test_document)
        print(f" Store result: {store_result}")

        # 2. Гибридный поиск
        print("\n Hybrid search...")
        search_results = await manager.hybrid_search("Какой размер платы концедента?")

        print(f" Search results: {len(search_results)} found")
        for i, result in enumerate(search_results[:3]):
            print(f" Result {i+1}:")
            print(f" Text: {result.text[:100]}...")
            print(f" Semantic score: {result.semantic_score:.3f}")
            print(f" Final score: {result.final_score:.3f}")
            print(f" Enhancements: {len(result.hybrid_enhancements)}")

        # 3. Статистика
        stats = manager.get_hybrid_stats()
        print(f"\n Hybrid stats: {stats}")

    asyncio.run(test_hybrid_storage())