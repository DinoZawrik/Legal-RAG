# Dockerfile для Giga-Embeddings Local Server
# Компактный образ для CPU-based inference

FROM python:3.11-slim

LABEL maintainer="LegalRAG Team"
LABEL description="Giga-Embeddings Local Server для векторизации русских юридических текстов"
LABEL version="2.0.0"

# Рабочая директория
WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements
COPY requirements.txt /app/requirements.txt

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование сервера
COPY embeddings_server.py /app/embeddings_server.py

# Создание директории для кеша моделей
RUN mkdir -p /app/.cache/huggingface

# Переменные окружения для HuggingFace
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
ENV TOKENIZERS_PARALLELISM=false

# Порт для API
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Запуск сервера
CMD ["python", "-u", "embeddings_server.py"]
