"""Маршруты поискового контура."""

from __future__ import annotations

import uuid
import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

if TYPE_CHECKING: # pragma: no cover
    from services.gateway.app import APIGateway

logger = logging.getLogger(__name__)


def register(gateway: "APIGateway") -> None:
    app = gateway.app

    @app.post("/api/query")
    async def process_query(http_request: Request):
        try:
            body = await http_request.json()
            query = body.get("query")
            max_results = body.get("max_results", 10)
            use_cache = body.get("use_cache", True)
            config = body.get("config")
            request_id = body.get("request_id") or uuid.uuid4().hex[:8]

            if not query:
                raise HTTPException(status_code=400, detail="Query is required")

            client_ip = http_request.client.host
            if not await gateway._check_rate_limit(client_ip):
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            search_service = gateway.registry.get_service("search_service")
            if not search_service:
                raise HTTPException(status_code=503, detail="Search service unavailable")

            search_request = {
                "type": "search",
                "query": query,
                "max_results": max_results,
                "use_cache": use_cache,
                "config": (config or {}).get("search_config", {}),
                "request_id": request_id,
            }

            # DEBUG: Log exact request being sent
            print(f"[GATEWAY->SEARCH] Request: type={search_request['type']}, query={query[:50]}, config={search_request['config']}")
            logger.info(f"[GATEWAY->SEARCH] Request: type={search_request['type']}, query={query[:50]}, config={search_request['config']}")

            search_response = await search_service.handle_request(search_request)

            # DEBUG: Log response received
            print(f"[SEARCH->GATEWAY] Response: success={search_response.get('success')}, results_count={len(search_response.get('data', {}).get('results', []))}")
            logger.info(f"[SEARCH->GATEWAY] Response: success={search_response.get('success')}, results_count={len(search_response.get('data', {}).get('results', []))}")
            if not search_response.get("success", True):
                error_msg = search_response.get("error", "Unknown search service error")
                raise HTTPException(status_code=500, detail=f"Search service error: {error_msg}")

            if "data" in search_response and isinstance(search_response["data"], dict):
                search_data = search_response["data"]
            else:
                search_data = search_response

            # Если SearchService уже сформировал ответ, используем его
            if search_data.get("answer"):
                return {
                    "query": query,
                    "answer": search_data.get("answer"),
                    "chunks_used": len(search_data.get("results", [])),
                    "request_id": request_id,
                    "metadata": {
                        "search_time": search_response.get("response_time", 0),
                        "inference_time": 0,
                        "total_time": search_response.get("response_time", 0),
                        "model_used": "search_service_integrated",
                        "search_metadata": search_data.get("metadata"),
                    },
                    "source_documents": search_data.get("results", []),
                    "success": True
                }

            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Передаем структурированные объекты с полными metadata
            context_chunks = []
            for chunk in search_data.get("results", []):
                # Извлекаем текст из разных возможных полей
                text = chunk.get("text") or chunk.get("document") or chunk.get("content", "")
                if text:
                    # Создаем enriched chunk object с сохранением всех metadata
                    enriched_chunk = {
                        "text": text,
                        "metadata": chunk.get("metadata", {}),
                        "similarity": chunk.get("similarity", chunk.get("distance", 0)),
                        "law_number": chunk.get("metadata", {}).get("law", "unknown"),
                        "article_number": chunk.get("metadata", {}).get("article", ""),
                        "document_type": chunk.get("metadata", {}).get("type", ""),
                        "chunk_id": chunk.get("id", ""),
                        # Добавляем key_sentences если есть
                        "key_sentences": chunk.get("key_sentences", "")
                    }
                    context_chunks.append(enriched_chunk)

            # PHASE 2.1: Log retrieved chunks for analysis
            gateway.logger.info(f"[ CHUNKS] Retrieved {len(context_chunks)} chunks for query: '{query[:100]}...'")
            for i, chunk in enumerate(context_chunks[:3], 1): # Log top 3
                law = chunk.get("law_number", "unknown")
                sim = chunk.get("similarity", 0)
                text_preview = chunk.get("text", "")[:150].replace("\n", " ")
                gateway.logger.info(f" Chunk {i}: Law={law}, Sim={sim:.3f}, Text='{text_preview}...'")
            if len(context_chunks) > 3:
                gateway.logger.info(f" ... and {len(context_chunks) - 3} more chunks")

            inference_service = gateway.registry.get_service("inference_service")
            if not inference_service:
                raise HTTPException(status_code=503, detail="Inference service unavailable")

            inference_request = {
                "type": "generate",
                "query": query,
                "context_chunks": context_chunks,
                "config": (config or {}).get("inference_config", {}),
                "request_id": request_id,
            }

            inference_response = await inference_service.handle_request(inference_request)

            if inference_response and inference_response.get("success", True):
                final_response = inference_response.get("data", inference_response)
            else:
                final_response = {
                    "answer": "Извините, произошла ошибка при генерации ответа.",
                    "chunks_used": len(context_chunks),
                    "generation_time": 0,
                    "model_used": "unknown",
                }

            final_response["source_documents"] = search_data.get("results", [])

            # ФАЗА 1.3: Формируем финальный ответ с verification
            sources_list = search_data.get("results", [])
            result = {
                "query": query,
                "answer": final_response.get("answer"),
                "chunks_used": len(sources_list), # FIX: Count from sources list
                "request_id": request_id,
                "success": True, # FIX: Добавлено поле success
                "sources": sources_list, # CRITICAL FIX: Return list of sources, not count
                "metadata": {
                    "search_time": search_response.get("response_time", 0),
                    "inference_time": final_response.get("generation_time", 0),
                    "total_time": search_response.get("response_time", 0)
                    + final_response.get("generation_time", 0),
                    "model_used": final_response.get("model_used"),
                    "search_metadata": search_data.get("metadata"),
                },
                "source_documents": final_response.get("source_documents"),
            }

            # Добавляем verification если есть
            if "verification" in final_response:
                result["verification"] = final_response["verification"]

            return result
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Query processing error: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/multimodal_test")
    async def multimodal_test():
        return {"status": "multimodal_test endpoint works", "message": "endpoint registration successful"}

    @app.post("/api/multimodal_search")
    async def handle_multimodal_search(http_request: Request):
        try:
            body = await http_request.json()
            query = body.get("query")
            max_results = body.get("max_results", 10)
            use_cache = body.get("use_cache", True)
            document_filter = body.get("document_filter")
            request_id = body.get("request_id") or uuid.uuid4().hex[:8]

            if not query:
                raise HTTPException(status_code=400, detail="Query is required")

            client_ip = http_request.client.host
            if not await gateway._check_rate_limit(client_ip):
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            search_service = gateway.registry.get_service("search_service")
            if not search_service:
                raise HTTPException(status_code=503, detail="Search service unavailable")

            multimodal_request = {
                "type": "multimodal_search",
                "query": query,
                "max_results": max_results or 10,
                "use_cache": use_cache,
                "document_filter": document_filter,
                "request_id": request_id,
            }

            response = await search_service.handle_request(multimodal_request)
            if response and response.get("success"):
                return response.get("data", {})

            return {
                "query": query,
                "results": [],
                "search_type": "multimodal",
                "total_results": 0,
                "message": "Enhanced multimodal search processing",
            }
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Multimodal search error: {exc}")
            return {
                "query": query,
                "results": [],
                "search_type": "multimodal",
                "total_results": 0,
                "error": str(exc),
            }

    @app.get("/api/debug_after_multimodal")
    async def debug_after_multimodal():
        return {"status": "after_multimodal", "message": "multimodal_endpoint_processed"}

    @app.post("/api/universal_legal_query")
    async def universal_legal_query(http_request: Request):
        try:
            body = await http_request.json()
            query = body.get("query")
            max_chunks = body.get("max_chunks", 7)
            strict_verification = body.get("strict_verification", True)
            config = body.get("config") or {}
            request_id = body.get("request_id") or uuid.uuid4().hex[:8]

            if not query:
                raise HTTPException(status_code=400, detail="Query is required")

            client_ip = http_request.client.host
            if not await gateway._check_rate_limit(client_ip):
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            gateway.logger.info(
                f"[TARGET] Processing universal legal query [{request_id}]: {query[:100]}..."
            )

            search_service = gateway.registry.get_service("search_service")
            if not search_service:
                raise HTTPException(status_code=503, detail="Search service unavailable")

            universal_request = {
                "type": "universal_legal_query",
                "query": query,
                "max_chunks": max_chunks,
                "strict_verification": strict_verification,
                "config": config,
                "request_id": request_id,
            }

            response = await search_service.handle_request(universal_request)
            if not response.get("success", True):
                error_msg = response.get("error", "Unknown search service error")
                raise HTTPException(status_code=500, detail=f"Universal legal query error: {error_msg}")

            result_data = response.get("data") if isinstance(response.get("data"), dict) else response

            return {
                "success": True,
                "query": query,
                "answer": result_data.get("answer"),
                "confidence_score": result_data.get("confidence_score"),
                "processing_time": result_data.get("processing_time"),
                "request_id": request_id,
                "metadata": result_data.get("metadata", {}),
                "debug_info": result_data.get("debug_info", {}),
                "system_type": "universal_legal_system",
            }
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Universal legal query error: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/hybrid_search")
    async def hybrid_search(http_request: Request):
        try:
            body = await http_request.json()
            query = body.get("query")
            max_results = body.get("max_results", 7)
            graph_enabled = body.get("graph_enabled", True)
            graph_depth = body.get("graph_depth", 2)
            config = body.get("config") or {}
            use_cache = body.get("use_cache", True)
            request_id = body.get("request_id") or uuid.uuid4().hex[:8]

            if not query:
                raise HTTPException(status_code=400, detail="Query is required")

            client_ip = http_request.client.host
            if not await gateway._check_rate_limit(client_ip):
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            gateway.logger.info(f"[RELOAD] Processing hybrid search [{request_id}]: {query[:100]}...")

            search_service = gateway.registry.get_service("search_service")
            if not search_service:
                raise HTTPException(status_code=503, detail="Search service unavailable")

            hybrid_request = {
                "type": "hybrid_search",
                "query": query,
                "max_results": max_results,
                "graph_enabled": graph_enabled,
                "graph_depth": graph_depth,
                "config": config,
                "use_cache": use_cache,
                "request_id": request_id,
            }

            response = await search_service.handle_request(hybrid_request)
            if not response.get("success", True):
                error_msg = response.get("error", "Unknown hybrid search error")
                raise HTTPException(status_code=500, detail=f"Hybrid search error: {error_msg}")

            result_data = response.get("data") if isinstance(response.get("data"), dict) else response

            return {
                "success": True,
                "query": query,
                "results": result_data.get("results", []),
                "total_results": result_data.get("total_results", 0),
                "hybrid_mode": result_data.get("hybrid_mode", "unknown"),
                "request_id": request_id,
                "metadata": result_data.get("metadata", {}),
                "system_type": "hybrid_legal_intelligence",
                "enhancements": {
                    "graph_enabled": graph_enabled,
                    "semantic_enhanced": True,
                    "structural_enhanced": graph_enabled,
                    "performance_improvement": result_data.get("metadata", {}).get(
                        "performance_improvement", 0.0
                    ),
                },
            }
        except HTTPException:
            raise
        except Exception as exc:
            gateway.logger.error(f"[CROSS_MARK] Hybrid search error: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))
