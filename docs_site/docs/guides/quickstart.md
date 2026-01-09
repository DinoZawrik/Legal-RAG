# Быстрый старт

Запуск LegalRAG системы за 10 минут.

---

## Требования

Перед началом убедитесь что у вас есть:

- [x] Python 3.11 или выше
- [x] Docker и Docker Compose
- [x] OpenAI API Key ([получить здесь](https://platform.openai.com/api-keys))
- [x] 8GB+ RAM (16GB рекомендуется)
- [x] 20GB+ свободного места на диске

---

## Установка

### Шаг 1: Клонирование репозитория

```bash
git clone https://github.com/DinoZawrik/Gov_wiki.git
cd Gov_wiki
```

### Шаг 2: Настройка окружения

```bash
# Копировать .env template
cp .env.example .env

# Отредактировать .env
nano .env  # или используйте любой редактор
```

!!! warning "Обязательные переменные"
    ```bash
    OPENAI_API_KEY=sk-...your_key_here...
    EMBEDDINGS_SERVER_URL=http://localhost:8001
    LLM_PROVIDER=openai
    ```

### Шаг 3: Установка зависимостей

```bash
pip install -r requirements.txt
```

### Шаг 4: Запуск Docker инфраструктуры

```bash
# Основные сервисы (PostgreSQL, Redis, ChromaDB)
docker-compose up -d

# Embeddings сервер (Giga-Embeddings)
docker-compose -f docker-compose.embeddings.yml up -d

# Neo4j (опционально, для Graph RAG)
docker-compose -f docker-compose.neo4j.yml up -d
```

Проверка:

```bash
docker ps | grep legalrag
# Должно быть 4-5 контейнеров в статусе "Up"
```

### Шаг 5: Загрузка тестовых документов

```bash
# Загрузить 115-FZ и 224-FZ (концессии и ГЧП)
python simple_chromadb_load.py

# Проверить количество документов
python check_chromadb_count.py
# Ожидается: ~250+ chunks
```

### Шаг 6: Запуск микросервисов

```bash
python start_microservices.py
```

Вы должны увидеть:

```
✅ API Gateway запущен на http://0.0.0.0:8080
✅ Search Service ready
✅ Inference Service ready
✅ Storage Service ready
✅ Cache Service ready
```

---

## Проверка работоспособности

### Health Check

```bash
curl http://localhost:8080/health/all
```

Ожидаемый ответ:

```json
{
  "status": "healthy",
  "services": {
    "gateway": "up",
    "search": "up",
    "inference": "up",
    "storage": "up",
    "cache": "up"
  },
  "databases": {
    "postgres": "connected",
    "redis": "connected",
    "chromadb": "connected",
    "neo4j": "connected"
  }
}
```

### Тестовый запрос

```bash
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Что такое концессионное соглашение?",
    "max_results": 5
  }'
```

Ожидаемый ответ:

```json
{
  "answer": "Концессионное соглашение — это договор между...",
  "sources": [
    {
      "law": "115-FZ",
      "article": "3",
      "text": "..."
    }
  ],
  "confidence": 0.95
}
```

---

## Запуск Telegram бота (опционально)

### Настройка

1. Создать бота через [@BotFather](https://t.me/BotFather)
2. Получить токен
3. Добавить в `.env`:

```bash
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_ADMIN_IDS=[your_telegram_id]
```

### Запуск

```bash
python bot/telegram_bot.py
```

---

## Запуск Admin Panel (опционально)

```bash
streamlit run admin_panel/admin_app.py --server.port 8090
```

Открыть в браузере: http://localhost:8090

Логин:
- Password: из переменной `ADMIN_PANEL_PASSWORD` в `.env`

---

## Что дальше?

- 📖 [Конфигурация](configuration.md) - детальная настройка
- 🏗️ [Архитектура](../architecture/overview.md) - понять как работает система
- 🔧 [API Reference](../api/search.md) - использование API
- 🚀 [Миграция v2.0](../migration/quickstart.md) - если обновляетесь с v1.0

---

## Troubleshooting

### Docker контейнеры не запускаются

```bash
# Проверить логи
docker logs legalrag_postgres
docker logs legalrag_embeddings

# Перезапустить
docker-compose down
docker-compose up -d
```

### Embeddings сервер не работает

```bash
# Проверить
curl http://localhost:8001/health

# Если ошибка - проверить логи
docker logs legalrag_embeddings -f
```

### ChromaDB пустая

```bash
# Загрузить документы заново
python simple_chromadb_load.py
```

Больше решений: [Troubleshooting Guide](../migration/troubleshooting.md)
