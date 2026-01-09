#!/usr/bin/env python3
"""
🔍 Search Service Advanced Handlers
Продвинутые обработчики поиска для микросервиса.

Включает функциональность:
- Универсальные правовые запросы
- Гибридный поиск (граф + семантика)
- Мультимодальный поисковый пайплайн
- Self-RAG интеграция
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.search_service_core import SearchServiceCore
from services.search_utilities import SearchUtilities
from core.hybrid_storage_manager import HybridQueryConfig

logger = logging.getLogger(__name__)


class SearchAdvancedHandlers(SearchServiceCore):
    """Продвинутые обработчики поиска для Search Service."""

    async def _handle_universal_legal_query(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка универсального правового запроса."""
        try:
            query = request.get("query", "").strip()
            if not query:
                return {
                    "success": False,
                    "error": "Query parameter is required"
                }

            max_chunks = request.get("max_chunks", 7)
            strict_verification = request.get("strict_verification", True)

            self.logger.info(f"[UNIVERSAL] Processing legal query: '{query[:50]}...'")

            # 🔧 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Сначала ищем документы через StorageManager
            context_documents = []
            if self.storage_manager:
                try:
                    search_results = await self.storage_manager.search_documents(
                        query=query,
                        limit=max_chunks * 2,  # Берем больше для лучшей фильтрации
                        use_cache=False
                    )
                    # Конвертируем результаты в формат для Universal Legal System
                    for doc in search_results:
                        context_documents.append({
                            'content': doc.get('text', doc.get('document', '')),
                            'metadata': doc.get('metadata', {}),
                            'similarity': doc.get('similarity', 0),
                            'source_document': doc.get('metadata', {}).get('law', 'unknown')
                        })
                    self.logger.info(f"[UNIVERSAL] Found {len(context_documents)} documents from ChromaDB")
                except Exception as e:
                    self.logger.error(f"[X] Error searching documents: {e}")

            # Используем Universal Legal System если доступен
            if self.universal_legal_system:
                try:
                    result = await self.universal_legal_system.process_query(
                        query=query,
                        context_documents=context_documents,  # Передаем найденные документы
                        max_chunks=max_chunks,
                        strict_verification=strict_verification
                    )

                    # Конвертируем UniversalQueryResult в словарь для API response
                    result_dict = {
                        "success": result.success,
                        "query": result.query,
                        "answer": result.answer,
                        "sources": result.source_documents or [],
                        "confidence": result.confidence_score,
                        "processing_time": result.processing_time,
                        "query_type": "universal_legal",
                        "timestamp": datetime.now().isoformat()
                    }

                    # Добавляем дополнительную информацию если есть
                    if result.entities_found:
                        result_dict["entities_found"] = len(result.entities_found)
                    if result.chunks_used:
                        result_dict["chunks_used"] = len(result.chunks_used)
                    if result.error_message:
                        result_dict["error"] = result.error_message

                    self.logger.info(f"[UNIVERSAL] Query processed with success: {result.success}")
                    return result_dict

                except Exception as e:
                    self.logger.error(f"[X] Universal Legal System error: {e}")
                    # Fallback to standard search
                    pass

            # Fallback: используем стандартный поиск
            self.logger.info("[UNIVERSAL] Falling back to standard search")
            fallback_request = {
                "type": "search",
                "query": query,
                "max_results": max_chunks
            }

            # Импортируем динамически чтобы избежать циклических импортов
            from services.search_request_handlers import SearchRequestHandlers
            handler = SearchRequestHandlers()
            handler.__dict__.update(self.__dict__)  # Копируем состояние

            result = await handler._handle_search_request(fallback_request)
            result["query_type"] = "universal_legal_fallback"
            
            # Убеждаемся что результат содержит нужные поля для API Gateway
            if not result.get("answer") and result.get("results"):
                # Если fallback поиск нашел результаты, но не сформировал ответ
                from services.search_utilities import SearchUtilities
                composed_answer = SearchUtilities._compose_contextual_answer(
                    query=query,
                    chunks=result.get("results", [])[:5],
                    legal_context={"entities": SearchUtilities.extract_legal_entities(query)}
                )
                result["answer"] = composed_answer

            return result

        except Exception as e:
            self.logger.error(f"[X] Error in universal legal query handler: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": request.get("query", ""),
                "query_type": "universal_legal",
                "timestamp": datetime.now().isoformat()
            }

    async def _handle_hybrid_search_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка гибридного поискового запроса (граф + семантика)."""
        try:
            query = request.get("query", "").strip()
            if not query:
                return {
                    "success": False,
                    "error": "Query parameter is required"
                }

            max_results = min(request.get("max_results", 10), 50)
            graph_enabled = request.get("graph_enabled", True)
            graph_depth = request.get("graph_depth", 2)
            graph_weight = request.get("graph_weight", 0.4)
            semantic_weight = request.get("semantic_weight", 0.6)

            self.logger.info(f"[HYBRID] Processing hybrid search: '{query[:50]}...' (graph: {graph_enabled})")

            # Проверяем доступность гибридного хранилища
            if not self.hybrid_storage or not graph_enabled:
                self.logger.info("[HYBRID] Falling back to semantic search only")
                fallback_request = {
                    "type": "search",
                    "query": query,
                    "max_results": max_results
                }

                from services.search_request_handlers import SearchRequestHandlers
                handler = SearchRequestHandlers()
                handler.__dict__.update(self.__dict__)

                result = await handler._handle_search_request(fallback_request)
                result["search_type"] = "semantic_only"
                return result

            # Создаем конфигурацию гибридного запроса
            hybrid_config = HybridQueryConfig(
                query=query,
                max_semantic_results=max_results,

                graph_depth=graph_depth,
                semantic_weight=semantic_weight,
                structural_weight=graph_weight,
                graph_enabled=graph_enabled
            )

            # Выполняем гибридный поиск
            try:
                hybrid_results = await self.hybrid_storage.hybrid_search(query, hybrid_config)

                # Постобработка результатов
                processed_results = await self._post_process_hybrid_results(hybrid_results, query)

                # Формируем ответ
                composed_answer = SearchUtilities._compose_contextual_answer(
                    query=query,
                    chunks=processed_results[:5],
                    legal_context={"entities": SearchUtilities.extract_legal_entities(query)}
                )

                result = {
                    "success": True,
                    "query": query,
                    "answer": composed_answer,
                    "results": processed_results,
                    "total_results": len(processed_results),
                    "search_type": "hybrid",
                    "graph_enabled": True,
                    "semantic_count": hybrid_results.get("semantic_count", 0),
                    "graph_count": hybrid_results.get("graph_count", 0),
                    "combined_count": len(processed_results),
                    "timestamp": datetime.now().isoformat()
                }

                self.logger.info(f"[HYBRID] Found {len(processed_results)} hybrid results")
                return result

            except Exception as e:
                self.logger.error(f"[X] Hybrid storage search error: {e}")
                # Fallback to semantic search
                fallback_request = {
                    "type": "search",
                    "query": query,
                    "max_results": max_results
                }

                from services.search_request_handlers import SearchRequestHandlers
                handler = SearchRequestHandlers()
                handler.__dict__.update(self.__dict__)

                result = await handler._handle_search_request(fallback_request)
                result["search_type"] = "semantic_fallback"
                result["hybrid_error"] = str(e)
                return result

        except Exception as e:
            self.logger.error(f"[X] Error in hybrid search handler: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": request.get("query", ""),
                "search_type": "hybrid",
                "timestamp": datetime.now().isoformat()
            }

    async def _handle_multimodal_search_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка мультимодального поискового запроса."""
        try:
            query = request.get("query", "").strip()
            if not query:
                return {
                    "success": False,
                    "error": "Query parameter is required"
                }

            max_results = min(request.get("max_results", 10), 50)
            include_images = request.get("include_images", False)
            include_tables = request.get("include_tables", True)
            include_presentations = request.get("include_presentations", True)

            self.logger.info(f"[MULTIMODAL] Processing multimodal search: '{query[:50]}...'")

            # Проверяем доступность мультимодального пайплайна
            if not self.multimodal_pipeline:
                self.logger.info("[MULTIMODAL] Pipeline not available, falling back to standard search")
                fallback_request = {
                    "type": "search",
                    "query": query,
                    "max_results": max_results
                }

                from services.search_request_handlers import SearchRequestHandlers
                handler = SearchRequestHandlers()
                handler.__dict__.update(self.__dict__)

                result = await handler._handle_search_request(fallback_request)
                result["search_type"] = "standard_fallback"
                return result

            # Выполняем мультимодальный поиск
            try:
                multimodal_config = {
                    "query": query,
                    "max_results": max_results,
                    "include_images": include_images,
                    "include_tables": include_tables,
                    "include_presentations": include_presentations,
                    "content_types": ["text", "table", "presentation"]
                }

                multimodal_results = await self.multimodal_pipeline.search(multimodal_config)

                # Постобработка результатов
                processed_results = await self._post_process_multimodal_results(multimodal_results, query)

                # Формируем ответ
                composed_answer = SearchUtilities._compose_contextual_answer(
                    query=query,
                    chunks=processed_results[:5],
                    legal_context={"entities": SearchUtilities.extract_legal_entities(query)}
                )

                # Анализ типов контента
                content_types = {}
                for result in processed_results:
                    content_type = result.get("metadata", {}).get("content_type", "text")
                    content_types[content_type] = content_types.get(content_type, 0) + 1

                result = {
                    "success": True,
                    "query": query,
                    "answer": composed_answer,
                    "results": processed_results,
                    "total_results": len(processed_results),
                    "search_type": "multimodal",
                    "content_distribution": content_types,
                    "modalities_used": {
                        "text": True,
                        "images": include_images,
                        "tables": include_tables,
                        "presentations": include_presentations
                    },
                    "timestamp": datetime.now().isoformat()
                }

                self.logger.info(f"[MULTIMODAL] Found {len(processed_results)} multimodal results")
                return result

            except Exception as e:
                self.logger.error(f"[X] Multimodal pipeline search error: {e}")
                # Fallback to standard search
                fallback_request = {
                    "type": "search",
                    "query": query,
                    "max_results": max_results
                }

                from services.search_request_handlers import SearchRequestHandlers
                handler = SearchRequestHandlers()
                handler.__dict__.update(self.__dict__)

                result = await handler._handle_search_request(fallback_request)
                result["search_type"] = "standard_fallback"
                result["multimodal_error"] = str(e)
                return result

        except Exception as e:
            self.logger.error(f"[X] Error in multimodal search handler: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": request.get("query", ""),
                "search_type": "multimodal",
                "timestamp": datetime.now().isoformat()
            }

    async def _post_process_hybrid_results(self, hybrid_results: Dict, query: str) -> List[Dict]:
        """Постобработка результатов гибридного поиска."""
        try:
            # Извлекаем результаты из гибридного ответа
            combined_results = hybrid_results.get("combined_results", [])

            processed_results = []
            for result in combined_results:
                processed_result = result.copy()

                # Добавляем информацию об источнике (граф или семантика)
                result_source = result.get("source", "unknown")
                processed_result["hybrid_source"] = result_source

                # Форматируем правовую ссылку
                metadata = result.get('metadata', {})
                law_reference = SearchUtilities._format_law_reference(metadata)
                if law_reference:
                    processed_result['law_reference'] = law_reference

                # Добавляем ключевые предложения
                text = result.get('text', result.get('document', ''))
                if text:
                    key_sentences = SearchUtilities._extract_key_sentences(text, max_sentences=2)
                    processed_result['key_sentences'] = key_sentences

                # Бонус за графовые связи
                if result_source == "graph":
                    original_score = result.get('similarity', result.get('score', 0))
                    processed_result['similarity'] = min(1.0, original_score + 0.05)  # Небольшой бонус
                    processed_result['graph_bonus'] = 0.05

                processed_results.append(processed_result)

            # Сортируем по релевантности
            processed_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)

            return processed_results

        except Exception as e:
            self.logger.error(f"[X] Error post-processing hybrid results: {e}")
            return hybrid_results.get("combined_results", [])

    async def _post_process_multimodal_results(self, multimodal_results: Dict, query: str) -> List[Dict]:
        """Постобработка результатов мультимодального поиска."""
        try:
            # Извлекаем результаты из мультимодального ответа
            results = multimodal_results.get("results", [])

            processed_results = []
            for result in results:
                processed_result = result.copy()

                # Определяем тип контента
                metadata = result.get('metadata', {})
                content_type = metadata.get('content_type', 'text')
                processed_result['content_type'] = content_type

                # Форматируем правовую ссылку
                law_reference = SearchUtilities._format_law_reference(metadata)
                if law_reference:
                    processed_result['law_reference'] = law_reference

                # Обработка по типу контента
                if content_type == 'table':
                    # Для таблиц добавляем структурированную информацию
                    table_data = metadata.get('table_data', {})
                    if table_data:
                        processed_result['table_summary'] = self._summarize_table_data(table_data)

                elif content_type == 'presentation':
                    # Для презентаций добавляем номер слайда
                    slide_number = metadata.get('slide_number')
                    if slide_number:
                        processed_result['slide_info'] = f"Слайд {slide_number}"

                # Добавляем ключевые предложения
                text = result.get('text', result.get('document', ''))
                if text:
                    key_sentences = SearchUtilities._extract_key_sentences(text, max_sentences=2)
                    processed_result['key_sentences'] = key_sentences

                # Бонус за редкие типы контента
                content_bonus = {
                    'table': 0.03,
                    'presentation': 0.02,
                    'image': 0.01
                }.get(content_type, 0)

                if content_bonus > 0:
                    original_score = result.get('similarity', 0)
                    processed_result['similarity'] = min(1.0, original_score + content_bonus)
                    processed_result['content_bonus'] = content_bonus

                processed_results.append(processed_result)

            # Сортируем по релевантности
            processed_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)

            return processed_results

        except Exception as e:
            self.logger.error(f"[X] Error post-processing multimodal results: {e}")
            return multimodal_results.get("results", [])

    def _summarize_table_data(self, table_data: Dict) -> str:
        """Создание краткого описания табличных данных."""
        try:
            rows = table_data.get('rows', 0)
            columns = table_data.get('columns', 0)
            headers = table_data.get('headers', [])

            summary_parts = []

            if rows and columns:
                summary_parts.append(f"Таблица {rows}x{columns}")

            if headers:
                summary_parts.append(f"Столбцы: {', '.join(headers[:3])}")
                if len(headers) > 3:
                    summary_parts.append("...")

            return " | ".join(summary_parts) if summary_parts else "Табличные данные"

        except Exception as e:
            self.logger.error(f"[X] Error summarizing table data: {e}")
            return "Табличные данные"

    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Реализация абстрактного метода process_request из BaseService.
        Маршрутизирует запросы к соответствующим обработчикам.
        """
        try:
            request_type = request.get("type", "")

            if request_type == "universal_legal_query":
                return await self._handle_universal_legal_query(request)
            elif request_type == "hybrid_search":
                return await self._handle_hybrid_search_request(request)
            elif request_type == "multimodal_search":
                return await self._handle_multimodal_search_request(request)
            else:
                # Fallback to parent search functionality
                return await super().process_request(request)

        except Exception as e:
            self.logger.error(f"[X] Error processing request: {e}")
            return {
                "success": False,
                "error": f"Failed to process request: {str(e)}",
                "request_type": request.get("type", "unknown")
            }