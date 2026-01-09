#!/usr/bin/env python3
"""
🔍 Search Service Request Handlers
Обработчики запросов для микросервиса поиска.

Включает функциональность:
- Основная обработка поисковых запросов
- Стандартный семантический поиск
- Управление конфигурацией
- Обработка статистики и кэша
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.search_service_core import SearchServiceCore
from services.search_utilities import SearchUtilities

logger = logging.getLogger(__name__)


class SearchRequestHandlers(SearchServiceCore):
    """Обработчики запросов для Search Service."""

    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Главная точка входа для обработки запросов."""
        try:
            request_type = request.get("type", "search")
            print(f"[PROCESS-REQUEST] SearchRequestHandlers.process_request() CALLED with type={request_type}")
            self.logger.info(f"[SEARCH] Processing request type: {request_type}")
            print(f"[ROUTING-DEBUG] About to route to handler for type: {request_type}")

            # Маршрутизация по типам запросов
            if request_type == "search":
                print(f"[ROUTING] Calling _handle_search_request() for type='search'")
                return await self._handle_search_request(request)
            elif request_type == "universal_legal_query":
                # Импортируем динамически чтобы избежать циклических импортов
                from services.search_advanced_handlers import SearchAdvancedHandlers
                handler = SearchAdvancedHandlers()
                handler.__dict__.update(self.__dict__)  # Копируем состояние
                return await handler._handle_universal_legal_query(request)
            elif request_type == "hybrid_search":
                from services.search_advanced_handlers import SearchAdvancedHandlers
                handler = SearchAdvancedHandlers()
                handler.__dict__.update(self.__dict__)
                return await handler._handle_hybrid_search_request(request)
            elif request_type == "multimodal_search":
                from services.search_advanced_handlers import SearchAdvancedHandlers
                handler = SearchAdvancedHandlers()
                handler.__dict__.update(self.__dict__)
                return await handler._handle_multimodal_search_request(request)
            elif request_type == "config":
                return await self._handle_config_request(request)
            elif request_type == "stats":
                return await self._handle_stats_request(request)
            elif request_type == "cache":
                return await self._handle_cache_request(request)
            else:
                return {
                    "success": False,
                    "error": f"Unknown request type: {request_type}",
                    "supported_types": ["search", "universal_legal_query", "hybrid_search", "multimodal_search", "config", "stats", "cache"]
                }

        except Exception as e:
            self.logger.error(f"[X] Error processing request: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def _handle_search_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка стандартного поискового запроса."""
        try:
            # Извлекаем параметры запроса
            query = request.get("query", "").strip()
            if not query:
                return {
                    "success": False,
                    "error": "Query parameter is required"
                }

            max_results = min(request.get("max_results", 10), 50)  # Ограничиваем максимум
            use_cache = request.get("use_cache", True)
            config = self._load_configuration()

            # DEBUG: Enhanced logging for diagnosis
            print(f"[SEARCH-HANDLER] _handle_search_request CALLED!")
            print(f"[SEARCH] Standard search for: '{query[:50]}...' (max_results: {max_results})")
            print(f"[DEBUG] Config loaded: use_graph={config.get('use_graph_search')}, use_hybrid={config.get('use_hybrid_search')}")
            self.logger.info(f"[SEARCH-HANDLER] _handle_search_request CALLED!")
            self.logger.info(f"[SEARCH] Standard search for: '{query[:50]}...' (max_results: {max_results})")
            self.logger.info(f"[DEBUG] Config loaded: use_graph_search={config.get('use_graph_search')}, use_hybrid_search={config.get('use_hybrid_search')}")

            # Проверяем кэш если разрешено
            cache_key = None
            if use_cache and self.cache:
                cache_key = f"search:{hash(query)}:{max_results}"
                cached_result = await self.cache.get(cache_key)
                if cached_result:
                    self.logger.info("[CACHE] Returning cached search result")
                    cached_result["cached"] = True
                    cached_result["success"] = True  # Убеждаемся что success присутствует
                    return cached_result

            # Выполняем поиск через storage manager
            search_results = []
            if self.storage_manager:
                try:
                    # DAY 2-3: Graph-Enhanced Hybrid Search (BM25 + Semantic + Neo4j Graph)
                    # Получаем ChromaDB collection из storage manager
                    chroma_collection = self.storage_manager.vector_store.collection

                    # Выбор метода поиска на основе конфигурации/окружения
                    use_graph_search = bool(config.get("use_graph_search", False))
                    use_hybrid_search = bool(config.get("use_hybrid_search", True))

                    # DEBUG: Log search method selection
                    self.logger.info(f"[DEBUG] Search method: graph={use_graph_search}, hybrid={use_hybrid_search}")

                    if use_graph_search:
                        # Graph-Enhanced Hybrid Search (самый продвинутый метод)
                        from core.graph_enhanced_search import graph_enhanced_hybrid_search

                        self.logger.info("[GRAPH+HYBRID] Using Graph-Enhanced Hybrid search (BM25+Semantic+Neo4j)")

                        graph_results = await graph_enhanced_hybrid_search(
                            chromadb_collection=chroma_collection,
                            query=query,
                            k=max_results,
                            graph_depth=1,  # Глубина графового обхода
                            max_related_per_article=3  # Макс. связанных статей
                        )

                        search_results = graph_results

                        self.logger.info(f"[GRAPH+HYBRID] Found {len(search_results)} results")

                        # Логируем TOP-3 scores
                        for i, result in enumerate(search_results[:3], 1):
                            bm25 = result.get('bm25_score', 0)
                            semantic = result.get('semantic_score', 0)
                            hybrid = result.get('hybrid_score', 0)
                            graph = result.get('graph_score', 0)
                            final = result.get('similarity', hybrid)
                            law = result.get('metadata', {}).get('law', 'N/A')
                            article = result.get('article_number', 'N/A')
                            related_count = len(result.get('graph_context', []))

                            self.logger.info(
                                f"  {i}. Final={final:.3f} (Hybrid={hybrid:.3f} + Graph={graph:.3f}) "
                                f"Law={law} Art={article}, Related={related_count}"
                            )

                    elif use_hybrid_search:
                        # Hybrid Search без графа (Day 1)
                        from core.hybrid_bm25_search import hybrid_search

                        print("[HYBRID-BM25] Using BM25 + Semantic hybrid search")
                        self.logger.info("[HYBRID-BM25] Using BM25 + Semantic hybrid search")

                        hybrid_results = await hybrid_search(
                            chromadb_collection=chroma_collection,
                            query=query,
                            k=max_results
                        )

                        search_results = hybrid_results

                        print(f"[HYBRID-BM25] Found {len(search_results)} results")
                        print(f"[DEBUG] Type of search_results: {type(search_results)}")
                        print(f"[DEBUG] search_results value: {search_results[:2] if search_results else 'EMPTY'}")
                        self.logger.info(f"[HYBRID-BM25] Found {len(search_results)} results")

                        # Логируем TOP-3 scores
                        for i, result in enumerate(search_results[:3], 1):
                            bm25 = result.get('bm25_score', 0)
                            semantic = result.get('semantic_score', 0)
                            hybrid = result.get('hybrid_score', 0)
                            law = result.get('metadata', {}).get('law', 'N/A')
                            self.logger.info(
                                f"  {i}. Hybrid={hybrid:.3f} (BM25={bm25:.3f}, Semantic={semantic:.3f}) Law={law}"
                            )
                    else:
                        # Fallback: обычный семантический поиск
                        self.logger.info("[SEMANTIC] Using standard semantic search")
                        enhanced_query = SearchUtilities.enhance_query_with_legal_terms(query)
                        search_results = await self.storage_manager.search_documents(
                            query=enhanced_query,
                            limit=max_results,
                            use_cache=False
                        )

                    self.logger.info(f"[SEARCH] Found {len(search_results)} results")
                except Exception as e:
                    self.logger.error(f"[X] Storage manager search error: {e}")
                    return {
                        "success": False,
                        "error": f"Search execution failed: {str(e)}"
                    }

            # Обработка результатов
            if not search_results:
                result = {
                    "success": True,  # ВАЖНО: это не ошибка, просто нет результатов
                    "query": query,
                    "results": [],
                    "total_results": 0,
                    "message": "No relevant documents found for your query",
                    "cached": False,
                    "processing_time": 0.0,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                # Постобработка результатов
                processed_results = await self._post_process_search_results(search_results, query)

                # Верификация цитат: фильтруем результаты с некорректными ссылками на статьи
                try:
                    verified_results = []
                    for r in processed_results:
                        text = r.get('text') or r.get('document', '')
                        if SearchUtilities.verify_citation_exists(text, r.get('metadata', {})):
                            verified_results.append(r)
                    if verified_results:
                        processed_results = verified_results
                except Exception as _e:
                    self.logger.warning(f"[VERIFY] Ошибка верификации цитат: {_e}")

                # 🎯 ФАЗА 1: Удален composed_answer - теперь Gateway всегда вызывает InferenceService
                # Это критично для работы системы верификации и Self-RAG
                # composed_answer = SearchUtilities._compose_contextual_answer(
                #     query=query,
                #     chunks=processed_results[:5],
                #     legal_context={"entities": SearchUtilities.extract_legal_entities(query)}
                # )

                result = {
                    "success": True,
                    "query": query,
                    # ❌ REMOVED: "answer" - пусть InferenceService генерирует ответы с верификацией
                    "results": processed_results,
                    "total_results": len(processed_results),
                    "cached": False,
                    "processing_time": 0.0,
                    "timestamp": datetime.now().isoformat(),
                    "legal_entities": SearchUtilities.extract_legal_entities(query)
                }

            # Кэшируем результат
            if use_cache and self.cache and cache_key:
                try:
                    await self.cache.set(cache_key, result, ttl=config.get("cache_ttl", 3600))
                except Exception as e:
                    self.logger.warning(f"[WARNING] Failed to cache result: {e}")

            return result

        except Exception as e:
            self.logger.error(f"[X] Error in search request handler: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": request.get("query", ""),
                "timestamp": datetime.now().isoformat()
            }

    async def _post_process_search_results(self, results: List[Dict], query: str) -> List[Dict]:
        """Постобработка результатов поиска."""
        try:
            processed_results = []

            for result in results:
                # Копируем оригинальный результат
                processed_result = result.copy()

                # Добавляем форматированную правовую ссылку
                metadata = result.get('metadata', {})
                law_reference = SearchUtilities._format_law_reference(metadata)
                if law_reference:
                    processed_result['law_reference'] = law_reference

                # Вычисляем бонус за актуальность
                document_date = metadata.get('document_date', '')
                recency_bonus = SearchUtilities._calculate_recency_bonus(document_date)

                # 🔧 FIX: Сохраняем оригинальные graph поля перед корректировкой
                has_graph_score = 'graph_score' in result
                has_graph_context = 'graph_context' in result

                # Корректируем similarity с учетом актуальности
                original_similarity = result.get('similarity', 0)
                adjusted_similarity = min(1.0, original_similarity + recency_bonus)
                processed_result['similarity'] = adjusted_similarity
                processed_result['recency_bonus'] = recency_bonus

                # 🔧 FIX: Восстанавливаем graph поля если они были (Graph-Enhanced Search)
                if has_graph_score:
                    processed_result['graph_score'] = result.get('graph_score', 0)
                if has_graph_context:
                    processed_result['graph_context'] = result.get('graph_context', [])

                # 🔧 FIX: Сохраняем также hybrid поля (BM25 + Semantic)
                if 'bm25_score' in result:
                    processed_result['bm25_score'] = result['bm25_score']
                if 'semantic_score' in result:
                    processed_result['semantic_score'] = result['semantic_score']
                if 'hybrid_score' in result:
                    processed_result['hybrid_score'] = result['hybrid_score']
                if 'article_number' in result:
                    processed_result['article_number'] = result['article_number']

                # Извлекаем ключевые предложения
                text = result.get('text', result.get('document', ''))
                if text:
                    key_sentences = SearchUtilities._extract_key_sentences(text, max_sentences=2)
                    processed_result['key_sentences'] = key_sentences

                # Добавляем правовые сущности из текста
                legal_entities = SearchUtilities.extract_legal_entities(text)
                if legal_entities:
                    processed_result['legal_entities'] = legal_entities[:5]  # Топ-5

                processed_results.append(processed_result)

            # Сортируем по скорректированной релевантности
            processed_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)

            return processed_results

        except Exception as e:
            self.logger.error(f"[X] Error in post-processing search results: {e}")
            return results  # Возвращаем оригинальные результаты в случае ошибки

    async def _handle_config_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса конфигурации."""
        try:
            action = request.get("action", "get")

            if action == "get":
                return {
                    "success": True,
                    "config": self.get_configuration_summary(),
                    "timestamp": datetime.now().isoformat()
                }
            elif action == "update":
                # В реальной реализации здесь можно обновлять конфигурацию
                return {
                    "success": False,
                    "error": "Config update not implemented yet"
                }
            else:
                return {
                    "success": False,
                    "error": f"Unknown config action: {action}",
                    "supported_actions": ["get", "update"]
                }

        except Exception as e:
            self.logger.error(f"[X] Error handling config request: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _handle_stats_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса статистики."""
        try:
            # Получаем статистику компонентов
            component_health = await self._additional_health_checks()
            storage_stats = SearchUtilities._get_storage_stats(self.storage_manager)

            stats = {
                "service_info": {
                    "name": self.service_name,
                    "uptime": datetime.now().isoformat(),
                    "status": "running"
                },
                "component_health": component_health,
                "storage_stats": storage_stats,
                "cache_stats": await self._get_cache_stats(),
                "performance_metrics": {
                    "average_response_time": "Not implemented",
                    "total_requests": "Not implemented",
                    "cache_hit_rate": "Not implemented"
                }
            }

            return {
                "success": True,
                "stats": stats,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"[X] Error handling stats request: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _handle_cache_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка запроса управления кэшем."""
        try:
            action = request.get("action", "status")

            if action == "status":
                cache_stats = await self._get_cache_stats()
                return {
                    "success": True,
                    "cache_stats": cache_stats,
                    "timestamp": datetime.now().isoformat()
                }
            elif action == "clear":
                if self.cache:
                    try:
                        cleared_count = await self.cache.clear_pattern("search:*")
                        return {
                            "success": True,
                            "message": f"Cleared {cleared_count} cache entries",
                            "timestamp": datetime.now().isoformat()
                        }
                    except Exception as e:
                        return {
                            "success": False,
                            "error": f"Failed to clear cache: {str(e)}"
                        }
                else:
                    return {
                        "success": False,
                        "error": "Cache not available"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Unknown cache action: {action}",
                    "supported_actions": ["status", "clear"]
                }

        except Exception as e:
            self.logger.error(f"[X] Error handling cache request: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_cache_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша."""
        try:
            if not self.cache:
                return {"status": "not_available"}

            # Здесь можно добавить реальную статистику кэша
            return {
                "status": "available",
                "type": type(self.cache).__name__,
                "details": "Cache statistics not implemented"
            }

        except Exception as e:
            self.logger.error(f"[X] Error getting cache stats: {e}")
            return {"status": "error", "error": str(e)}