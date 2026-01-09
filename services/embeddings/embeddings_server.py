#!/usr/bin/env python3
"""
🤖 Giga-Embeddings Local Server
FastAPI HTTP API для локальной генерации embeddings через Giga-Embeddings-instruct модель.

Архитектура:
- Модель: Giga-Embeddings-instruct (Sber AI) или sbert_large_nlu_ru
- Output: 768-dimensional vectors (совместимость с ChromaDB!)
- Inference: CPU-based (без GPU для упрощения развертывания)
- API: OpenAI-совместимый endpoint /v1/embeddings

Использование:
    # Запуск:
    uvicorn embeddings_server:app --host 0.0.0.0 --port 8001

    # Тест:
    curl -X POST http://localhost:8001/v1/embeddings \
      -H "Content-Type: application/json" \
      -d '{"input": ["Что такое концессионное соглашение?"]}'

Ресурсы:
- RAM: ~4-6 GB для модели + inference
- CPU: ~1-2 сек на батч из 50 текстов
- Storage: ~2-3 GB для модели на диске
"""

import logging
import time
from typing import List, Optional, Union
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальная переменная для модели
model: Optional[SentenceTransformer] = None

# Конфигурация модели
MODEL_NAME = "ai-forever/sbert_large_nlu_ru"  # Можно заменить на Giga-Embeddings
EMBEDDING_DIMENSION = 1024  # Размерность для sbert_large_nlu_ru
DEVICE = "cpu"  # Используем CPU (можно "cuda" если есть GPU)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для загрузки модели при старте"""
    global model

    logger.info(f"🚀 Loading embeddings model: {MODEL_NAME}")
    logger.info(f"📊 Device: {DEVICE}")

    try:
        start_time = time.time()

        # Загрузка модели
        model = SentenceTransformer(MODEL_NAME, device=DEVICE)

        # Проверка размерности
        test_embedding = model.encode(["test"], show_progress_bar=False)
        actual_dim = test_embedding.shape[1]

        load_time = time.time() - start_time

        logger.info(f"✅ Model loaded successfully in {load_time:.2f}s")
        logger.info(f"📐 Embedding dimension: {actual_dim}")
        logger.info(f"💾 Model memory footprint: ~{torch.cuda.memory_allocated() / 1024**3:.2f} GB" if torch.cuda.is_available() else "💾 CPU mode")

        global EMBEDDING_DIMENSION
        EMBEDDING_DIMENSION = actual_dim

    except Exception as e:
        logger.error(f"❌ Failed to load model: {e}")
        raise

    yield

    # Cleanup при shutdown
    logger.info("🛑 Shutting down embeddings server")
    model = None


app = FastAPI(
    title="Giga-Embeddings Local Server",
    description="OpenAI-compatible embeddings API для LegalRAG",
    version="2.0.0",
    lifespan=lifespan
)


class EmbeddingRequest(BaseModel):
    """Запрос на генерацию embeddings (OpenAI-compatible)"""
    input: Union[str, List[str]] = Field(..., description="Текст или список текстов для векторизации")
    model: str = Field(default="giga-embeddings-instruct", description="Название модели (игнорируется)")
    encoding_format: Optional[str] = Field(default="float", description="Формат encoding (float или base64)")


class EmbeddingData(BaseModel):
    """Один результат embedding"""
    object: str = "embedding"
    embedding: List[float]
    index: int


class EmbeddingResponse(BaseModel):
    """Ответ с embeddings (OpenAI-compatible)"""
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: dict


class ErrorResponse(BaseModel):
    """Ответ с ошибкой"""
    error: dict


@app.post("/v1/embeddings", response_model=EmbeddingResponse, responses={500: {"model": ErrorResponse}})
async def create_embeddings(request: EmbeddingRequest):
    """
    Генерация embeddings через локальную модель.

    OpenAI-compatible endpoint:
    - POST /v1/embeddings
    - Body: {"input": ["text1", "text2"], "model": "giga-embeddings-instruct"}
    - Response: {"data": [{"embedding": [...], "index": 0}], "model": "...", "usage": {...}}
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    # Нормализация input (str → List[str])
    texts = [request.input] if isinstance(request.input, str) else request.input

    if not texts:
        raise HTTPException(status_code=400, detail="Input cannot be empty")

    logger.info(f"📥 Encoding {len(texts)} text(s)")

    try:
        start_time = time.time()

        # Генерация embeddings через SentenceTransformer
        embeddings = model.encode(
            texts,
            batch_size=32,  # Батчинг для эффективности
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True  # L2 normalization для cosine similarity
        )

        inference_time = time.time() - start_time

        # Конвертация в list для JSON
        embeddings_list = embeddings.tolist()

        logger.info(f"✅ Generated {len(embeddings_list)} embedding(s) in {inference_time:.3f}s ({inference_time/len(texts):.3f}s per text)")

        # Формирование OpenAI-compatible response
        response = EmbeddingResponse(
            object="list",
            data=[
                EmbeddingData(
                    object="embedding",
                    embedding=emb,
                    index=idx
                )
                for idx, emb in enumerate(embeddings_list)
            ],
            model=MODEL_NAME,
            usage={
                "prompt_tokens": sum(len(text.split()) for text in texts),  # Приблизительная оценка
                "total_tokens": sum(len(text.split()) for text in texts)
            }
        )

        return response

    except Exception as e:
        logger.error(f"❌ Encoding error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Encoding failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if model is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "loading",
                "model_loaded": False,
                "message": "Model is still loading"
            }
        )

    return {
        "status": "healthy",
        "model_loaded": True,
        "model_name": MODEL_NAME,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "device": DEVICE
    }


@app.get("/info")
async def model_info():
    """Информация о модели"""
    return {
        "model_name": MODEL_NAME,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "device": DEVICE,
        "model_loaded": model is not None,
        "max_sequence_length": model.max_seq_length if model else None
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик ошибок"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": str(exc),
                "type": type(exc).__name__
            }
        }
    )


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting Giga-Embeddings Local Server")
    logger.info(f"📍 Endpoint: http://0.0.0.0:8001/v1/embeddings")
    logger.info(f"🔍 Health check: http://0.0.0.0:8001/health")

    uvicorn.run(
        "embeddings_server:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=False  # Production mode
    )
