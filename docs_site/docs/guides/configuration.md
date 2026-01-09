# Конфигурация

Полное руководство по настройке LegalRAG системы.

---

## Переменные окружения

Все настройки хранятся в файле `.env`. Используйте `.env.example` как шаблон.

### 🔑 API Ключи (ОБЯЗАТЕЛЬНО)

=== "OpenAI (PRIMARY после миграции v2.0)"
    ```bash
    # Основной ключ
    OPENAI_API_KEY=sk-...your_key_here...

    # Дополнительные ключи для ротации (опционально)
    OPENAI_API_KEY_1=sk-...key1...
    OPENAI_API_KEY_2=sk-...key2...
    OPENAI_API_KEY_3=sk-...key3...
    ```

=== "Gemini (LEGACY - обратная совместимость)"
    ```bash
    GEMINI_API_KEY=your_gemini_key_here
    GOOGLE_API_KEY=your_gemini_key_here
    GOOGLE_API_KEY_EXTRACTION=your_gemini_key_here
    GOOGLE_API_KEY_AGENT=your_gemini_key_here
    ```

=== "Telegram Bot"
    ```bash
    TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
    TELEGRAM_ADMIN_IDS=[123456789,987654321]
    ```

---

## 🤖 AI Models Configuration

### LLM Provider (МИГРАЦИЯ v2.0)

```bash
# Выбор провайдера: openai | gemini (legacy)
LLM_PROVIDER=openai

# Модели для разных задач
EXTRACTION_MODEL_NAME=gpt-4-turbo      # Извлечение текста
AGENT_MODEL_NAME=gpt-4-turbo           # Reasoning agent
INDUSTRY_CLASSIFICATION_MODEL=gpt-4-turbo  # Классификация
```

!!! tip "Рекомендации по моделям"
    - **gpt-4-turbo**: Лучшее качество для юридических документов
    - **gpt-4**: Более дешевая альтернатива с хорошим качеством
    - **gpt-3.5-turbo**: Бюджетный вариант (не рекомендуется для production)

### Embeddings Provider

```bash
# Провайдер: local | google (legacy)
EMBEDDING_MODEL_PROVIDER=local

# URL локального сервера
EMBEDDINGS_SERVER_URL=http://localhost:8001

# Модель и размерность
EMBEDDING_MODEL_NAME=giga-embeddings-instruct
EMBEDDING_DIMENSION=1024  # 768 для Gemini (legacy)
```

!!! warning "Размерность векторов"
    После миграции на Giga-Embeddings размерность изменится с 768 на 1024.
    Потребуется перегенерация всех векторов в ChromaDB.

---

## 💾 База данных

### PostgreSQL

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=legal_rag_db
POSTGRES_USER=legal_rag_user
POSTGRES_PASSWORD=your_secure_password

# Connection pool
POSTGRES_MIN_POOL_SIZE=5
POSTGRES_MAX_POOL_SIZE=20
POSTGRES_CONNECTION_TIMEOUT=30
```

### Redis

```bash
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_TIMEOUT=5
```

### ChromaDB

```bash
# HTTP connection
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_USE_HTTP=true
CHROMA_SSL=false
CHROMA_TIMEOUT=30

# Collections
COLLECTION_NAME=documents
DEFAULT_COLLECTION_NAME=documents

# Local path (если не используете Docker)
CHROMA_DB_PATH=./legalrag_chroma_db
```

### Neo4j (Graph RAG)

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

---

## 🎯 RAG System Configuration

### Основные параметры

```bash
# Использовать оптимальную конфигурацию
USE_OPTIMAL_RAG=true
RAG_CONFIG_NAME=optimal

# Retrieval settings
MAX_CHUNKS=7                  # Максимум chunks в контексте
SIMILARITY_THRESHOLD=0.65     # Порог релевантности
RETRIEVER_K=5                 # Количество кандидатов
REGULATORY_SEARCH_K=8         # Для регуляторных документов
```

### Hybrid Search

```bash
# Веса для гибридного поиска
SEMANTIC_WEIGHT=0.6   # Векторный поиск (60%)
KEYWORD_WEIGHT=0.4    # BM25 поиск (40%)
```

!!! info "Оптимальные веса"
    60/40 соотношение доказало лучшую эффективность на русских юридических текстах.
    BM25 компенсирует слабость embeddings на терминах.

### Caching

```bash
# Стратегия кэширования
CACHE_STRATEGY=adaptive       # adaptive | aggressive | minimal
CACHE_TTL=3600               # Время жизни кэша (секунды)
SEMANTIC_THRESHOLD=0.75      # Порог для семантического матчинга
REGULATORY_CACHE_TTL=7200    # Для регуляторных документов
```

---

## 📄 Document Processing

### Chunking Settings

```bash
# Размеры chunks
CHUNK_SIZE=1000              # Стандартные документы
CHUNK_OVERLAP=200            # Перекрытие chunks

# Регуляторные документы
REGULATORY_CHUNK_SIZE=800
REGULATORY_CHUNK_OVERLAP=150
```

### File Upload

```bash
# Ограничения размера
TELEGRAM_MAX_FILE_SIZE=20        # MB для Telegram
REGULATORY_MAX_FILE_SIZE=10      # MB для регуляторных
MAX_FILE_SIZE=10485760           # Байты (10MB)

# Директория загрузки
UPLOAD_DIR=./legalrag_documents
```

### Processing Timeouts

```bash
REGULATORY_PROCESSING_TIMEOUT=300        # 5 минут
PRESENTATION_PROCESSING_TIMEOUT=1800     # 30 минут
```

---

## 🎭 Microservices Configuration

### Gateway

```bash
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8080
ENVIRONMENT=development     # development | production
DEBUG=false
```

### Service Management

```bash
STARTUP_TIMEOUT=30          # Время на запуск сервиса
HEALTH_CHECK_INTERVAL=60    # Интервал health checks
```

### Monitoring

```bash
MONITORING_ENABLED=true
ENABLE_PERFORMANCE_MONITORING=false
ENABLE_REGULATORY_PERFORMANCE_MONITORING=true
```

---

## 🔧 Performance Settings

### Database

```bash
DB_POOL_SIZE=5              # Размер пула соединений
DB_QUERY_TIMEOUT=30         # Таймаут запросов (секунды)
```

### Rate Limiting

```bash
RATE_LIMIT_REQUESTS=10      # Запросов на окно
RATE_LIMIT_WINDOW=60        # Размер окна (секунды)
```

### Concurrency

```bash
MAX_RETRY_ATTEMPTS=2
MAX_CONCURRENT_PROCESSING=3
CACHE_MAXSIZE=100
```

---

## 📋 Logging & Debugging

### Log Configuration

```bash
LOG_LEVEL=INFO              # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=json             # json | text
ENABLE_DEBUG_LOGS=true
```

!!! warning "Production"
    В production рекомендуется:
    ```bash
    LOG_LEVEL=WARNING
    ENABLE_DEBUG_LOGS=false
    DEBUG=false
    ```

---

## 📱 Telegram Bot Settings

### Chat Management

```bash
TELEGRAM_ENABLE_CHAT_HISTORY=false
TELEGRAM_MAX_MESSAGES_TO_CLEAR=50
TELEGRAM_CHAT_HISTORY_TTL=3600
```

### UI Settings

```bash
TELEGRAM_DOCUMENTS_PER_PAGE=5
TELEGRAM_INDUSTRIES_PER_PAGE=8
TELEGRAM_REGULATORY_DOCS_PER_PAGE=3
```

### Features

```bash
TELEGRAM_MAX_SELECTED_INDUSTRIES=5
TELEGRAM_ENABLE_INDUSTRY_FILTERING=true
```

---

## 🏷️ Classification & Processing

### Document Classification

```bash
DEFAULT_DOC_TYPE=presentation
AUTO_CLASSIFICATION_ENABLED=false
DEFAULT_INDUSTRIES=general,finance,healthcare,education,transport
```

### Regulatory Processing

```bash
ENABLE_AUTO_INDUSTRY_DETECTION=true
ENABLE_REGULATORY_METADATA_SEARCH=true
REGULATORY_VECTOR_WEIGHT=0.6
REGULATORY_BM25_WEIGHT=0.4
REGULATORY_BM25_CACHE_TTL=3600
```

---

## 🔧 Feature Flags

```bash
ENABLE_REGULATORY_PIPELINE=true
ENABLE_VISION_PROCESSING=true
ENABLE_ADVANCED_SEARCH=true
ENABLE_STATISTICS=true
```

---

## 🌐 Admin Panel Configuration

### Authentication

```bash
# Простая аутентификация (single admin)
ADMIN_PANEL_PASSWORD=your-secure-password-here
ADMIN_JWT_SECRET=your-jwt-secret-key-here
ADMIN_PANEL_SESSION_TIMEOUT=28800  # 8 hours
```

### Access Control

```bash
# JSON массив Telegram ID с правами загрузки
TELEGRAM_ADMIN_IDS=[123456789,987654321]
```

---

## 🛠️ Проверка конфигурации

### Валидация .env файла

```bash
# Проверить все переменные
python -c "
from core.infrastructure_suite import get_config
config = get_config()
print('✅ Configuration loaded successfully')
print(f'LLM Provider: {config.llm_provider}')
print(f'Embeddings: {config.embedding_model_provider}')
"
```

### Тест подключений

```bash
# Проверить все базы данных
python -c "
import asyncio
from core.data_storage_suite import UnifiedStorageManager

async def test():
    storage = UnifiedStorageManager()
    results = await storage.initialize()
    print(results)

asyncio.run(test())
"
```

Ожидаемый вывод:
```json
{
  "postgres": true,
  "redis": true,
  "vector_store": true
}
```

---

## 🔍 Troubleshooting

### .env не загружается

```bash
# Проверить путь
ls -la .env

# Проверить права
chmod 600 .env

# Проверить синтаксис
cat .env | grep -v '^#' | grep '='
```

### Переменные не подставляются

```bash
# Проверить загрузку
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY'))"
```

### Конфликты версий

```bash
# Переустановить зависимости
pip install --upgrade --force-reinstall -r requirements.txt
```

---

## 📖 Что дальше?

- 🚀 [Миграция v2.0](../migration/quickstart.md) - Переход на GPT-5 + Giga-Embeddings
- 🏗️ [Архитектура](../architecture/overview.md) - Понять структуру системы
- 🔧 [API Reference](../api/search.md) - Использование API
