#!/usr/bin/env python3
"""
 Search Service Core
Основная инфраструктура и инициализация микросервиса поиска.

Включает функциональность:
- Базовый класс SearchServiceCore
- Инициализация всех компонентов поиска
- Управление жизненным циклом сервиса
- Проверки здоровья и конфигурации
"""

import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

from services.base import BaseService
from services.inference_service import create_inference_service
from core.storage_coordinator import create_storage_coordinator, StorageCoordinator
from core.rag_optimizer import get_rag_optimizer, RAGOptimizer
# MIGRATED FROM: core.intelligent_cache (deprecated) → NEW: core.cache
from core.cache import IntelligentCache

async def get_intelligent_cache() -> IntelligentCache:
    """Legacy compatibility."""
    return IntelligentCache()
from core.universal_legal_system import get_universal_legal_system, UniversalLegalSystem
from core.hybrid_storage_manager import get_hybrid_storage, HybridStorageManager
# MIGRATED FROM: core.multimodal_search_pipeline (deprecated) → NEW: core.multimodal
from core.multimodal import MultimodalSearchPipeline

def create_multimodal_search_pipeline(*args, **kwargs):
    """Legacy compatibility."""
    return MultimodalSearchPipeline(*args, **kwargs)
from core.precision_legal_prompts import PrecisionLegalPromptEngine
from core.advanced_structured_prompts import AdvancedStructuredPromptEngine
from core.robust_legal_prompts import RobustLegalPromptEngine
from core.neo4j_real_connection import Neo4jRealConnection

logger = logging.getLogger(__name__)


class SearchServiceCore(BaseService):
    """
    Базовый класс микросервиса поиска и извлечения информации.

    Объединяет:
    - Семантический поиск через UnifiedStorageManager
    - RAG оптимизацию
    - Интеллектуальное кэширование
    - Гибридное хранилище (граф + семантика)
    - Мультимодальный поиск
    """

    def __init__(self):
        super().__init__("search_service")

        # Компоненты поиска
        self.storage_manager: Optional[UnifiedStorageManager] = None
        self.rag_optimizer: Optional[RAGOptimizer] = None
        self.cache: Optional[IntelligentCache] = None
        self.universal_legal_system: Optional[UniversalLegalSystem] = None

        # НОВОЕ: Гибридное хранилище (граф + семантика)
        self.hybrid_storage: Optional[HybridStorageManager] = None

        # НОВОЕ: Neo4j граф для правовых связей
        self.neo4j_connection: Optional[Neo4jRealConnection] = None

        # НОВОЕ: Мультимодальный поисковый пайплайн
        self.multimodal_pipeline: Optional[MultimodalSearchPipeline] = None

        # НОВОЕ: AI-сервис для генерации ответов
        self.inference_service = None

        # НОВОЕ: Сверхточные промпты для правовых вопросов
        self.precision_prompt_engine: Optional[PrecisionLegalPromptEngine] = None

        # НОВОЕ: Продвинутые структурированные промпты (JSON формат)
        self.structured_prompt_engine: Optional[AdvancedStructuredPromptEngine] = None

        # НОВОЕ: Устойчивые промпты (высокая стабильность)
        self.robust_prompt_engine: Optional[RobustLegalPromptEngine] = None

        # УЛЬТРА-ОПТИМИЗИРОВАННАЯ конфигурация для 80%+ успешности
        self.default_config = {
            "rag_config": "optimal",
            "max_results": 15,  # Увеличено для лучшего покрытия
            "use_cache": True,
            "cache_ttl": 3600,
            "semantic_threshold": 0.6,  # Снижен для большего покрытия
            "chunk_overlap": 0.3,  # Больше перекрытия
            "require_law_reference": True,  # Обязательная ссылка на закон
            "use_reranking": True,  # Переранжирование результатов
            "use_graph_search": False,  # DAY 2-3: Graph-Enhanced Search (DISABLED - Neo4j not running)
            "use_hybrid_search": True,  # DAY 1: Hybrid BM25 + Semantic (PRIMARY METHOD)
            "graph_weight": 0.4,  # Вес графовой базы
            "semantic_weight": 0.6  # Вес семантического поиска
        }

    async def initialize(self) -> None:
        """Инициализация Search Service."""
        try:
            self.logger.info("[SEARCH] Initializing Search Service...")

            # Инициализация унифицированного хранилища
            self.logger.info("[RELOAD] Loading Unified Storage Manager...")
            self.storage_manager = await create_storage_coordinator()

            # Инициализация RAG оптимизатора
            self.logger.info("[RELOAD] Loading RAG Optimizer...")
            self.rag_optimizer = get_rag_optimizer()

            # Инициализация кэша
            self.logger.info("[RELOAD] Loading Intelligent Cache...")
            self.cache = await get_intelligent_cache()

            # НОВОЕ: Инициализация Universal Legal System
            self.logger.info("[TARGET] Loading Universal Legal System...")
            self.universal_legal_system = await get_universal_legal_system()

            # НОВОЕ: Инициализация Hybrid Storage Manager
            self.logger.info("[RELOAD] Loading Hybrid Storage Manager (Graph + Semantic)...")
            try:
                self.hybrid_storage = await get_hybrid_storage()
                self.logger.info("[CHECK_MARK_BUTTON] Hybrid Storage Manager loaded successfully")
            except Exception as e:
                self.logger.warning(f"[WARNING] Hybrid Storage Manager failed to load: {e}, falling back to standard storage")
                self.hybrid_storage = None

            # НОВОЕ: Инициализация Multimodal Search Pipeline
            self.logger.info("[TARGET] Loading Multimodal Search Pipeline...")
            try:
                # Получаем ChromaDB клиент из storage_manager
                chroma_client = None
                redis_client = None

                if self.storage_manager and hasattr(self.storage_manager, 'vector_store'):
                    chroma_client = getattr(self.storage_manager.vector_store, 'client', None)

                if self.cache and hasattr(self.cache, 'redis_client'):
                    redis_client = self.cache.redis_client

                self.multimodal_pipeline = await create_multimodal_search_pipeline(
                    chroma_client=chroma_client,
                    redis_client=redis_client
                )
                self.logger.info("[CHECK_MARK_BUTTON] Multimodal Search Pipeline loaded successfully")
            except Exception as e:
                self.logger.warning(f"[WARNING] Multimodal Search Pipeline failed to load: {e}")
                self.multimodal_pipeline = None

            # НОВОЕ: Инициализация AI Inference Service
            self.logger.info("[TARGET] Loading AI Inference Service...")
            try:
                self.inference_service = await create_inference_service()
                self.logger.info("[CHECK_MARK_BUTTON] AI Inference Service loaded successfully")
            except Exception as e:
                self.logger.warning(f"[WARNING] AI Inference Service failed to load: {e}")
                self.inference_service = None

            # НОВОЕ: Инициализация Neo4j подключения
            self.logger.info("[TARGET] Loading Neo4j Real Connection...")
            try:
                self.neo4j_connection = Neo4jRealConnection()
                connected = await self.neo4j_connection.connect()
                if not connected:
                    self.neo4j_connection = None
                self.logger.info("[CHECK_MARK_BUTTON] Neo4j Real Connection loaded successfully")
            except Exception as e:
                self.logger.warning(f"[WARNING] Neo4j Real Connection failed to load: {e}")
                self.neo4j_connection = None

            # НОВОЕ: Инициализация Precision Legal Prompt Engine
            self.logger.info("[TARGET] Loading Precision Legal Prompt Engine...")
            try:
                self.precision_prompt_engine = PrecisionLegalPromptEngine()
                self.logger.info("[CHECK_MARK_BUTTON] Precision Legal Prompt Engine loaded successfully")
            except Exception as e:
                self.logger.warning(f"[WARNING] Precision Legal Prompt Engine failed to load: {e}")
                self.precision_prompt_engine = None

            # НОВОЕ: Инициализация Advanced Structured Prompt Engine
            self.logger.info("[TARGET] Loading Advanced Structured Prompt Engine...")
            try:
                self.structured_prompt_engine = AdvancedStructuredPromptEngine()
                self.logger.info("[CHECK_MARK_BUTTON] Advanced Structured Prompt Engine loaded successfully")
            except Exception as e:
                self.logger.warning(f"[WARNING] Advanced Structured Prompt Engine failed to load: {e}")
                self.structured_prompt_engine = None

            # НОВОЕ: Инициализация Robust Legal Prompt Engine
            self.logger.info("[TARGET] Loading Robust Legal Prompt Engine...")
            try:
                self.robust_prompt_engine = RobustLegalPromptEngine()
                self.logger.info("[CHECK_MARK_BUTTON] Robust Legal Prompt Engine loaded successfully")
            except Exception as e:
                self.logger.warning(f"[WARNING] Robust Legal Prompt Engine failed to load: {e}")
                self.robust_prompt_engine = None

            self.logger.info("[CHECK_MARK_BUTTON] Search Service initialization completed!")

        except Exception as e:
            self.logger.error(f"[X] Failed to initialize Search Service: {e}")
            raise

    async def start(self) -> None:
        """Запуск Search Service."""
        await super().start()
        self.logger.info("[ROCKET] Search Service started successfully")

    async def stop(self) -> None:
        """Остановка Search Service."""
        await super().stop()
        self.logger.info("[STOP_SIGN] Search Service stopped")

    async def cleanup(self) -> None:
        """Очистка ресурсов Search Service."""
        try:
            if self.neo4j_connection:
                await self.neo4j_connection.close()

            if self.cache:
                await self.cache.close()

            self.logger.info("[CHECK_MARK_BUTTON] Search Service cleanup completed")
        except Exception as e:
            self.logger.error(f"[X] Error during Search Service cleanup: {e}")

    def _load_configuration(self) -> Dict[str, Any]:
        """Загрузка конфигурации сервиса."""
        config = self.default_config.copy()

        # Дополнительные настройки для оптимизации
        config.update({
            "chunk_strategy": "overlap_preserve",
            "ranking_algorithm": "hybrid_boost",
            "context_window": 2048,
            "max_chunk_size": 512,
            "min_similarity_score": 0.3,
            "enable_cross_references": True,
            "legal_entity_extraction": True,
            "date_priority_boost": 0.1
        })

        # Переопределение флагов из переменных окружения
        def _env_to_bool(name: str, default: bool) -> bool:
            val = os.getenv(name)
            if val is None:
                return default
            return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}

        config["use_graph_search"] = _env_to_bool("USE_GRAPH_SEARCH", config.get("use_graph_search", False))
        config["use_hybrid_search"] = _env_to_bool("USE_HYBRID_SEARCH", config.get("use_hybrid_search", True))

        return config

    async def _additional_health_checks(self) -> Dict[str, Any]:
        """Дополнительные проверки здоровья для Search Service."""
        health_status = {
            "storage_manager": self.storage_manager is not None,
            "rag_optimizer": self.rag_optimizer is not None,
            "cache": self.cache is not None,
            "universal_legal_system": self.universal_legal_system is not None,
            "hybrid_storage": self.hybrid_storage is not None,
            "multimodal_pipeline": self.multimodal_pipeline is not None,
            "inference_service": self.inference_service is not None,
            "neo4j_connection": self.neo4j_connection is not None,
            "precision_prompts": self.precision_prompt_engine is not None,
            "structured_prompts": self.structured_prompt_engine is not None,
            "robust_prompts": self.robust_prompt_engine is not None
        }

        # Подсчет активных компонентов
        active_components = sum(1 for status in health_status.values() if status)
        total_components = len(health_status)

        health_status["active_components"] = active_components
        health_status["total_components"] = total_components
        health_status["component_health_percentage"] = (active_components / total_components) * 100

        # Проверка критических компонентов
        critical_components = ["storage_manager", "rag_optimizer"]
        critical_status = all(health_status.get(comp, False) for comp in critical_components)
        health_status["critical_components_ok"] = critical_status

        return health_status

    def get_configuration_summary(self) -> Dict[str, Any]:
        """Получение сводки конфигурации."""
        config = self._load_configuration()
        return {
            "service_name": self.service_name,
            "default_config": config,
            "component_status": {
                "storage_manager": "" if self.storage_manager else "",
                "rag_optimizer": "" if self.rag_optimizer else "",
                "cache": "" if self.cache else "",
                "hybrid_storage": "" if self.hybrid_storage else "",
                "multimodal_pipeline": "" if self.multimodal_pipeline else "",
                "inference_service": "" if self.inference_service else "",
                "neo4j_connection": "" if self.neo4j_connection else ""
            },
            "optimization_features": [
                "RAG optimization",
                "Intelligent caching",
                "Hybrid graph+semantic search",
                "Multimodal search pipeline",
                "Precision legal prompts",
                "Cross-reference extraction",
                "Date priority boosting"
            ]
        }

    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Базовая реализация обработки запросов для SearchServiceCore.
        Должна быть переопределена в наследниках для специфичной логики.
        """
        self.logger.warning(f"[BASE] Default process_request called for {request.get('type', 'unknown')} request")
        return {
            "success": False,
            "error": "This method should be implemented in derived classes",
            "request_type": request.get("type", "unknown"),
            "service": self.service_name
        }