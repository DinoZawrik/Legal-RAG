# Быстрый старт миграции

Миграция на GPT-5 + Локальный Giga-Embeddings за 5 шагов.

**Версия**: 2.0 | **Дата**: 13.10.2025 | **Статус**: ✅ Готово к миграции

---

## ⚡ 5 шагов до запуска

### Шаг 1: Получить API ключи

```bash
# OpenAI API key (для GPT-4/GPT-5)
# https://platform.openai.com/api-keys
```

Добавить в `.env`:
```bash
OPENAI_API_KEY=sk-...your_key_here...
```

---

### Шаг 2: Запустить Embeddings сервер

```bash
# Запуск Docker контейнера
docker-compose -f docker-compose.embeddings.yml up -d

# Дождаться загрузки модели (30-60 сек)
docker logs legalrag_embeddings -f
```

Ожидаемый вывод:
```
INFO: Model loaded successfully
INFO: Application startup complete
INFO: Uvicorn running on http://0.0.0.0:8001
```

!!! tip "Первый запуск"
    При первом запуске модель скачается (~2GB). Это займет 5-10 минут в зависимости от скорости интернета.

---

### Шаг 3: Проверить размерность векторов

```bash
python test_embeddings_server.py
```

**КРИТИЧНО**: Проверить вывод!

=== "Размерность = 768"
    ```
    ✅ Размерность: 768
    ✅ Совместимо с ChromaDB
    ```
    → Переходите к шагу 4

=== "Размерность = 1024"
    ```
    ⚠️ Размерность: 1024
    ⚠️ Требуется миграция векторов
    ```
    → Запустите миграцию:
    ```bash
    python scripts/migrate_embeddings_to_giga_local.py
    ```
    Займет 10-30 минут для 250+ документов

---

### Шаг 4: Обновить зависимости

```bash
pip install openai langchain-openai
```

Опционально (удалить старые Gemini зависимости):
```bash
pip uninstall google-genai langchain-google-genai
```

---

### Шаг 5: Тестовый запрос

```bash
# Запустить систему
python start_microservices.py

# В другом терминале - тест API
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Что такое концессионное соглашение?", "max_results": 5}'
```

**Ожидаемый результат**: Ответ от GPT-4 на основе локальных embeddings ✅

---

## 📊 Что было сделано

### Созданные файлы (19 новых)

**Embeddings Server**:

- [services/embeddings/embeddings_server.py](../../services/embeddings/embeddings_server.py) - FastAPI HTTP server
- [services/embeddings/Dockerfile](../../services/embeddings/Dockerfile) - Docker образ
- [services/embeddings/requirements.txt](../../services/embeddings/requirements.txt) - зависимости
- [docker-compose.embeddings.yml](../../docker-compose.embeddings.yml) - оркестрация

**HTTP Clients**:

- [core/giga_local_embeddings_client.py](../../core/giga_local_embeddings_client.py) - async client для embeddings
- [core/openai_inference_client.py](../../core/openai_inference_client.py) - async client для GPT-4/GPT-5

**Migration Scripts**:

- [test_embeddings_server.py](../../test_embeddings_server.py) - комплексный тест embeddings
- [scripts/migrate_embeddings_to_giga_local.py](../../scripts/migrate_embeddings_to_giga_local.py) - миграция ChromaDB векторов
- [check_migration_readiness.py](../../check_migration_readiness.py) - проверка готовности

**Документация**:

- [docs/MIGRATION_GPT5_GIGA_LOCAL.md](../../docs/MIGRATION_GPT5_GIGA_LOCAL.md) - полный план миграции
- [MIGRATION_QUICKSTART.md](../../MIGRATION_QUICKSTART.md) - quick start guide

### Обновленные файлы (9 обновлено)

**Core Integration**:

- [core/vector_store_manager.py](../../core/vector_store_manager.py) - локальный embeddings сервер
- [core/ai_inference_core.py](../../core/ai_inference_core.py) - OpenAI inference
- [core/api_key_manager.py](../../core/api_key_manager.py) - multi-provider (OpenAI + Gemini legacy)
- [core/langgraph_rag_workflow.py](../../core/langgraph_rag_workflow.py) - LangGraph с GPT-4

**Configuration**:

- [.env.example](../../.env.example) - новые переменные окружения
- [requirements.txt](../../requirements.txt) - OpenAI зависимости
- [CLAUDE.md](../../CLAUDE.md) - обновлена документация

---

## 🔍 Проверка готовности

### Checklist

```bash
# 1. Embeddings сервер работает?
curl http://localhost:8001/health
```
Ожидается: `{"status": "healthy", "model_loaded": true}`

```bash
# 2. Размерность проверена?
python test_embeddings_server.py
```
Ожидается: `Размерность: 768 или 1024`

```bash
# 3. OpenAI API key установлен?
echo $OPENAI_API_KEY
```
Ожидается: `sk-...`

```bash
# 4. ChromaDB работает?
docker ps | grep chroma
```
Ожидается: `legalrag_chromadb (up)`

```bash
# 5. Документы загружены?
python check_chromadb_count.py
```
Ожидается: `>0 документов`

---

## ⚠️ Что НЕ нужно делать

!!! danger "Не делайте это"
    - ❌ **НЕ пересоздавайте ChromaDB** если размерность = 768
    - ❌ **НЕ удаляйте Docker volumes** до полной проверки
    - ❌ **НЕ запускайте миграцию** без проверки размерности

---

## 🐛 Troubleshooting

### Embeddings сервер не запускается

```bash
# Проверить логи
docker logs legalrag_embeddings

# Частые проблемы:
# - Нехватка RAM: увеличить memory limit в docker-compose.embeddings.yml
# - Модель не скачалась: проверить internet connection
# - Порт занят: изменить port mapping (8001 → 8002)
```

Решение для нехватки памяти:
```yaml
# В docker-compose.embeddings.yml
services:
  legalrag_embeddings:
    deploy:
      resources:
        limits:
          memory: 8G  # Увеличить с 6G до 8G
```

### ChromaDB пустая

```bash
# Загрузить тестовые документы
python simple_chromadb_load.py

# Проверить количество
python check_chromadb_count.py
```

### OpenAI API ошибка "Invalid API key"

```bash
# Проверить формат ключа
echo $OPENAI_API_KEY | grep "^sk-"

# Обновить .env
nano .env
# Раскомментировать и заполнить: OPENAI_API_KEY=sk-...

# Перезапустить сервисы
docker-compose restart
```

### Тесты падают с "Connection refused"

```bash
# Проверить все сервисы
curl http://localhost:8080/health/all

# Restart docker stack
docker-compose down && docker-compose up -d
```

Подробнее: [Troubleshooting Guide](troubleshooting.md)

---

## 📈 Ожидаемые результаты

### Performance

**Embeddings Generation** (100 текстов):

| Метод | Время | Скорость | Ускорение |
|-------|-------|----------|-----------|
| Gemini API | ~30 сек | 0.3s/text | 1x |
| **Giga-Local** | ~5-10 сек | 0.05-0.1s/text | **3-6x** ⚡ |

**Answer Generation** (1 запрос):

| Модель | Время | Качество |
|--------|-------|----------|
| Gemini 2.5 Flash | ~2-3 сек | Baseline |
| **GPT-4 Turbo** | ~3-5 сек | Улучшено на русском |

### Quality

**40-Question Test**:

| Модель | Score | Pass Rate |
|--------|-------|-----------|
| Baseline (Gemini) | 39/40 | 97.5% |
| **Target (GPT-4)** | ≥38/40 | ≥95% |
| Acceptable | ≥36/40 | ≥90% |

---

## 🚦 Следующие шаги

### Immediate (первые 24 часа)

- [ ] Запустить `test_40_natural_answers.py`
- [ ] Сравнить результаты с baseline
- [ ] Проверить Telegram бота
- [ ] Мониторить логи на ошибки

### Short-term (1 неделя)

- [ ] Оптимизировать промпты под GPT-4
- [ ] Настроить температуру и max_tokens
- [ ] A/B тестирование качества ответов
- [ ] Измерить стоимость OpenAI API

### Long-term (1 месяц)

- [ ] Полностью удалить Gemini зависимости
- [ ] Оптимизировать embeddings модель (quantization?)
- [ ] Внедрить GPT-5 (когда будет доступен)
- [ ] Обновить документацию

---

## 💰 Оценка стоимости

### OpenAI Pricing

**GPT-4 Turbo**:

- Input: $10 per 1M tokens
- Output: $30 per 1M tokens

**Пример** (1000 запросов/день):

- Средний промпт: ~500 tokens input + ~200 tokens output
- Стоимость: ~$7-10 в день
- **Месяц**: ~$210-300

**Embeddings** (локальные):

- Стоимость: **$0** (бесплатно!)
- Экономия vs OpenAI embeddings: ~$50-100/месяц

!!! tip "Снижение затрат"
    - Используйте caching (67% hit rate) для уменьшения количества запросов
    - Оптимизируйте размер промптов
    - Рассмотрите gpt-3.5-turbo для простых задач

---

## 📚 Дополнительные ресурсы

- [Migration Overview](overview.md) - Обзор миграции
- [Full Migration Plan](full-plan.md) - Детальный план
- [Troubleshooting](troubleshooting.md) - Решение проблем
- [OpenAI API Documentation](https://platform.openai.com/docs/)

---

**Готово к миграции!** 🎉 Следуйте шагам выше и запускайте систему ✅
