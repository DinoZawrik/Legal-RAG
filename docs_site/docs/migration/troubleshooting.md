# Troubleshooting миграции

Решение типичных проблем при миграции на GPT-5 + Giga-Embeddings.

---

## 🔴 Embeddings Server

### Сервер не запускается

**Симптомы**:
```bash
docker logs legalrag_embeddings
# Error: Cannot allocate memory
```

**Решение 1**: Увеличить память

```yaml
# docker-compose.embeddings.yml
services:
  legalrag_embeddings:
    deploy:
      resources:
        limits:
          memory: 8G  # Увеличить с 6G
```

**Решение 2**: Проверить доступную память
```bash
free -h
# Если <8GB свободно - остановить другие контейнеры
docker stop legalrag_neo4j  # Neo4j использует ~2GB
```

---

### Модель не скачивается

**Симптомы**:
```bash
docker logs legalrag_embeddings
# Error downloading model: Connection timeout
```

**Решение**: Ручная загрузка модели

```bash
# На хосте
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('ai-forever/sbert_large_nlu_ru')
print('Model downloaded successfully')
"

# Перезапуск контейнера
docker-compose -f docker-compose.embeddings.yml restart
```

---

### Порт 8001 занят

**Симптомы**:
```bash
docker-compose -f docker-compose.embeddings.yml up -d
# Error: port 8001 already allocated
```

**Решение 1**: Найти процесс
```bash
# Linux/Mac
lsof -i :8001
kill -9 <PID>

# Windows
netstat -ano | findstr :8001
taskkill /PID <PID> /F
```

**Решение 2**: Изменить порт
```yaml
# docker-compose.embeddings.yml
ports:
  - "8002:8001"  # Изменить внешний порт

# .env
EMBEDDINGS_SERVER_URL=http://localhost:8002
```

---

### Health check падает

**Симптомы**:
```bash
curl http://localhost:8001/health
# Connection refused
```

**Диагностика**:
```bash
# 1. Проверить статус контейнера
docker ps -a | grep embeddings

# 2. Проверить логи
docker logs legalrag_embeddings --tail 50

# 3. Проверить сеть
docker network inspect legalrag_network
```

**Решение**:
```bash
# Перезапуск с полной пересборкой
docker-compose -f docker-compose.embeddings.yml down
docker-compose -f docker-compose.embeddings.yml up -d --build
```

---

## 🟡 ChromaDB Migration

### Размерность векторов не совпадает

**Симптомы**:
```bash
python test_embeddings_server.py
# Размерность: 1024
# ChromaDB: 768
# ❌ Несовместимо!
```

**Решение**: Миграция векторов
```bash
# Запустить миграцию (10-30 минут)
python scripts/migrate_embeddings_to_giga_local.py

# Проверить результат
python check_chromadb_count.py
```

---

### Миграция зависла

**Симптомы**:
```bash
python scripts/migrate_embeddings_to_giga_local.py
# Processing chunks: 150/250...
# (замерло на 10+ минут)
```

**Решение 1**: Проверить логи embeddings сервера
```bash
docker logs legalrag_embeddings -f
# Если OOM (Out Of Memory) - увеличить RAM
```

**Решение 2**: Уменьшить batch size
```python
# scripts/migrate_embeddings_to_giga_local.py
BATCH_SIZE = 10  # Было 32
```

**Решение 3**: Перезапустить с продолжением
```bash
# Скрипт сохраняет прогресс, можно перезапустить
python scripts/migrate_embeddings_to_giga_local.py --resume
```

---

### ChromaDB пустая после миграции

**Симптомы**:
```bash
python check_chromadb_count.py
# Count: 0
```

**Решение 1**: Проверить коллекцию
```python
python -c "
import chromadb
client = chromadb.HttpClient(host='localhost', port=8000)
collections = client.list_collections()
print([c.name for c in collections])
"
```

**Решение 2**: Перезагрузить документы
```bash
python simple_chromadb_load.py
```

---

## 🟢 OpenAI Integration

### Invalid API key

**Симптомы**:
```bash
curl -X POST http://localhost:8080/api/query ...
# Error: Incorrect API key provided
```

**Решение 1**: Проверить формат ключа
```bash
echo $OPENAI_API_KEY
# Должно начинаться с "sk-"

# Проверить .env
cat .env | grep OPENAI_API_KEY
```

**Решение 2**: Проверить ключ на OpenAI
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**Решение 3**: Пересоздать ключ
- Зайти на https://platform.openai.com/api-keys
- Revoke старый ключ
- Создать новый
- Обновить `.env`

---

### Rate limit exceeded

**Симптомы**:
```bash
# Error: Rate limit reached for gpt-4-turbo
```

**Решение 1**: Добавить ротацию ключей
```bash
# .env
OPENAI_API_KEY_1=sk-...key1...
OPENAI_API_KEY_2=sk-...key2...
OPENAI_API_KEY_3=sk-...key3...
```

**Решение 2**: Использовать gpt-3.5-turbo
```bash
# .env
AGENT_MODEL_NAME=gpt-3.5-turbo
```

**Решение 3**: Включить caching
```bash
# .env
CACHE_STRATEGY=aggressive
CACHE_TTL=7200  # 2 часа
```

---

### Timeout errors

**Симптомы**:
```bash
# Error: Request timeout after 30s
```

**Решение**: Увеличить таймауты
```python
# core/openai_inference_client.py
self.llm = ChatOpenAI(
    model="gpt-4-turbo",
    openai_api_key=api_key,
    timeout=60,  # Было 30
    max_retries=3
)
```

---

## 🔵 System Integration

### Microservices не стартуют

**Симптомы**:
```bash
python start_microservices.py
# Error: Failed to start Search Service
```

**Диагностика**:
```bash
# Проверить все зависимости
curl http://localhost:8001/health  # Embeddings
curl http://localhost:8000/api/v1/heartbeat  # ChromaDB
docker exec legalrag_postgres pg_isready  # PostgreSQL
docker exec legalrag_redis redis-cli ping  # Redis
```

**Решение**: Последовательный запуск
```bash
# 1. Запустить embeddings
docker-compose -f docker-compose.embeddings.yml up -d
sleep 30

# 2. Проверить health
curl http://localhost:8001/health

# 3. Запустить микросервисы
python start_microservices.py
```

---

### Dependencies conflicts

**Симптомы**:
```bash
pip install openai langchain-openai
# ERROR: Cannot install openai==1.5 and langchain-openai==0.1
```

**Решение 1**: Чистая установка
```bash
pip uninstall openai langchain-openai langchain
pip install -r requirements.txt
```

**Решение 2**: Виртуальное окружение
```bash
python -m venv venv_migration
source venv_migration/bin/activate  # Linux/Mac
venv_migration\Scripts\activate  # Windows

pip install -r requirements.txt
```

---

### Import errors

**Симптомы**:
```python
from core.giga_local_embeddings_client import GigaLocalEmbeddingsClient
# ModuleNotFoundError: No module named 'aiohttp'
```

**Решение**:
```bash
pip install aiohttp aiofiles
```

---

## 🟣 Performance Issues

### Slow embeddings generation

**Симптомы**:
```bash
python test_embeddings_server.py
# 100 texts: 30 seconds (should be 5-10s)
```

**Решение 1**: Проверить CPU usage
```bash
docker stats legalrag_embeddings
# Если CPU < 50% - увеличить cores
```

```yaml
# docker-compose.embeddings.yml
deploy:
  resources:
    limits:
      cpus: '6'  # Было 4
```

**Решение 2**: Увеличить batch size
```python
# services/embeddings/embeddings_server.py
model.encode(texts, batch_size=64)  # Было 32
```

---

### High memory usage

**Симптомы**:
```bash
docker stats
# legalrag_embeddings: 7.5GB / 8GB
```

**Решение 1**: Quantization
```python
# services/embeddings/embeddings_server.py
from sentence_transformers.quantization import quantize_embeddings

# После encode:
embeddings = quantize_embeddings(embeddings, precision="int8")
```

**Решение 2**: Ограничить concurrent requests
```python
# services/embeddings/embeddings_server.py
@app.on_event("startup")
async def startup():
    app.state.limiter = asyncio.Semaphore(3)  # Max 3 concurrent
```

---

### Slow answer generation

**Симптомы**:
```bash
curl -X POST http://localhost:8080/api/query ...
# Takes 60+ seconds (should be ~30s)
```

**Диагностика**:
```bash
# Проверить каждый компонент
time python -c "
import asyncio
from core.giga_local_embeddings_client import GigaLocalEmbeddingsClient

async def test():
    client = GigaLocalEmbeddingsClient('http://localhost:8001')
    start = asyncio.get_event_loop().time()
    await client.generate_embeddings(['test'])
    print(f'Embeddings: {asyncio.get_event_loop().time() - start:.2f}s')

asyncio.run(test())
"
```

**Решение**: Проверить bottleneck
- Embeddings slow? → Увеличить CPU/RAM
- OpenAI slow? → Проверить network latency
- Search slow? → Оптимизировать ChromaDB queries

---

## 🟠 Data Integrity

### Vectors mismatch

**Симптомы**:
```bash
# Search results are worse than before migration
```

**Диагностика**:
```bash
# Проверить размерность в ChromaDB
python -c "
import chromadb
client = chromadb.HttpClient(host='localhost', port=8000)
collection = client.get_collection('documents')
print(f'Count: {collection.count()}')
# Взять sample
result = collection.get(limit=1, include=['embeddings'])
print(f'Dimension: {len(result[\"embeddings\"][0])}')
"
```

**Решение**: Полная перегенерация
```bash
# 1. Удалить старую коллекцию
python -c "
import chromadb
client = chromadb.HttpClient(host='localhost', port=8000)
client.delete_collection('documents')
"

# 2. Перезагрузить документы
python simple_chromadb_load.py
```

---

### Missing documents

**Симптомы**:
```bash
python check_chromadb_count.py
# Count: 150 (should be 250+)
```

**Решение**:
```bash
# Проверить файлы
ls файлы_для_теста/
# Должно быть: 115-FZ.pdf, 224-FZ.pdf

# Перезагрузить
python simple_chromadb_load.py --force-reload
```

---

## 🔧 Rollback Plan

### Откат на Gemini (emergency)

**Быстрый откат (5 минут)**:

```bash
# 1. Остановить embeddings
docker-compose -f docker-compose.embeddings.yml down

# 2. Откатить .env
git checkout .env

# 3. Перезапуск
python start_microservices.py
```

**Полный откат (30 минут)**:

```bash
# 1. Откатить код
git checkout core/vector_store_manager.py
git checkout core/ai_inference_core.py
git checkout core/langgraph_rag_workflow.py

# 2. Откатить зависимости
git checkout requirements.txt
pip install -r requirements.txt

# 3. Перегрузить векторы (если были мигрированы)
# Потребуется перезапуск с Gemini embeddings
python simple_chromadb_load.py --use-gemini
```

---

## 📞 Getting Help

### Логи для диагностики

Соберите следующие логи перед обращением за помощью:

```bash
# 1. Embeddings server
docker logs legalrag_embeddings --tail 100 > logs_embeddings.txt

# 2. Microservices
python start_microservices.py 2>&1 | tee logs_microservices.txt

# 3. Docker stats
docker stats --no-stream > logs_docker_stats.txt

# 4. System info
uname -a > logs_system.txt
free -h >> logs_system.txt
df -h >> logs_system.txt
```

### Полезные команды

```bash
# Health check всей системы
curl http://localhost:8080/health/all | jq

# Проверка embeddings
python test_embeddings_server.py

# Полный тест
python test_40_natural_answers.py
```

---

## ✅ Checklist после решения проблем

- [ ] Embeddings server работает: `curl http://localhost:8001/health`
- [ ] Размерность корректна: `python test_embeddings_server.py`
- [ ] ChromaDB не пустая: `python check_chromadb_count.py`
- [ ] OpenAI ключ валиден: `curl https://api.openai.com/v1/models ...`
- [ ] Микросервисы запущены: `curl http://localhost:8080/health/all`
- [ ] Тест проходит: `python test_40_natural_answers.py`

---

## 📚 Дополнительные ресурсы

- [Migration Overview](overview.md) - Обзор миграции
- [Quick Start](quickstart.md) - Быстрый старт
- [Full Plan](full-plan.md) - Детальный план
- [Architecture](../architecture/overview.md) - Архитектура системы
