# LegalRAG — Система анализа юридических документов

<p align="center">
  <a href="README.md">🇬🇧 English</a> |
  <strong>🇷🇺 Русский</strong>
</p>

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](https://docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agentic-purple.svg)](https://langchain-ai.github.io/langgraph/)

> Production-ready RAG система для анализа юридических документов с гибридным поиском, графовой базой знаний и агентным workflow.

## Ключевые возможности

- **Гибридный BM25 + Семантический поиск** — комбинация 60/40 для оптимального поиска по юридической терминологии
- **LangGraph Agentic Workflow** — 5-узловая CRAG-архитектура с самокритикой и автоматическим fallback
- **Neo4j Graph RAG** — 95+ юридических определений со связями для расширенного контекста
- **Многоуровневый Fallback** — Vector DB → Graph DB → Web Search автоматический переход
- **BGE Reranker v2-m3** — кросс-энкодер ререйнкинг для повышения точности
- **Микросервисная архитектура** — 5 независимых сервисов с мониторингом и graceful shutdown
- **Telegram бот + Админ-панель** — полноценный UI с JWT авторизацией

## Архитектура

```
                    +------------------+
                    |   API Gateway    |
                    |   (FastAPI)      |
                    +--------+---------+
                             |
        +--------------------+--------------------+
        |                    |                    |
+-------v-------+    +-------v-------+    +-------v-------+
| Search Service|    |Inference Svc  |    | Storage Svc   |
| (Hybrid BM25) |    | (Gemini/GPT)  |    | (Multi-DB)    |
+-------+-------+    +-------+-------+    +-------+-------+
        |                    |                    |
        +--------------------+--------------------+
                             |
              +--------------+--------------+
              |              |              |
        +-----v----+  +------v-----+  +-----v----+
        | ChromaDB |  | PostgreSQL |  |  Neo4j   |
        | (Vector) |  | (Metadata) |  | (Graph)  |
        +----------+  +------------+  +----------+
```

### LangGraph Workflow

```
retrieve_initial -> grade_documents -> repair_retrieve -> generate_answer -> critique_answer
       |                  |                  |                  |                  |
   Гибридный         LLM Оценка        Реформуляция       Gemini Flash      Само-проверка
   BM25 + Graph      качества          + Web Search       Генерация         Валидация
```

## Технологический стек

| Категория | Технология |
|-----------|------------|
| **LLM** | Google Gemini 2.5 Flash / OpenAI GPT-4 |
| **Embeddings** | Gemini text-embedding-004 (768-dim) |
| **Vector DB** | ChromaDB с async клиентом |
| **Graph DB** | Neo4j 5.x с APOC |
| **Relational DB** | PostgreSQL 16 |
| **Cache** | Redis 7 |
| **Framework** | FastAPI + LangGraph + Aiogram |
| **Reranker** | BGE Reranker v2-m3 (sentence-transformers) |

## Быстрый старт

### Требования
- Python 3.11+
- Docker & Docker Compose
- Gemini API Key (есть бесплатный tier)

### 1. Клонирование и настройка

```bash
git clone https://github.com/YOUR_USERNAME/LegalRAG.git
cd LegalRAG

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или: venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Конфигурация окружения

```bash
cp .env.example .env
# Отредактируйте .env с вашими ключами:
#   GEMINI_API_KEY=your_key_here
#   TELEGRAM_BOT_TOKEN=your_token_here
```

### 3. Запуск инфраструктуры

```bash
# Запуск PostgreSQL, Redis, ChromaDB
docker-compose up -d

# Запуск Neo4j (опционально, для graph-enhanced search)
docker-compose -f docker-compose.neo4j.yml up -d
```

### 4. Загрузка данных и запуск

```bash
# Загрузка документов в vector store
python scripts/reset_and_ingest_documents.py

# Запуск микросервисов
python scripts/start_microservices.py
```

### 5. Проверка

```bash
# Health check
curl http://localhost:8080/health/all

# Тестовый запрос
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Что такое концессионное соглашение?", "max_results": 5}'
```

## Производительность

| Метрика | Значение |
|---------|----------|
| Точность (40-вопросный бенчмарк) | **97.5%** |
| Среднее время ответа | ~33 сек |
| Пропускная способность API | 1500 RPD (с ротацией ключей) |
| Cache hit rate | 67% на похожих запросах |

## Структура проекта

```
LegalRAG/
├── core/                    # Основные модули
│   ├── hybrid_bm25_search.py    # Основной поисковый движок
│   ├── langgraph_rag_workflow.py # Агентный RAG workflow
│   ├── reranker.py              # BGE Reranker
│   └── settings.py              # Конфигурация
├── services/                # Микросервисы
│   ├── gateway/                 # API Gateway
│   ├── search_service_core.py   # Оркестрация поиска
│   └── inference_service.py     # LLM инференс
├── bot/                     # Telegram бот
├── admin_panel/             # Streamlit админ-панель
├── tools/                   # RAG инструменты (graph, web)
├── docker-compose.yml       # Инфраструктура
└── scripts/                 # Скрипты запуска
```

## Ключевые инновации

### 1. Гибридный поиск для юридических текстов
BM25 keyword matching (60%) в сочетании с семантическими embeddings (40%) решает проблему низкого качества embeddings на русской юридической терминологии.

### 2. Graph-Enhanced Fallback
Когда качество векторного поиска недостаточно, система автоматически обращается к Neo4j графовой базе данных за определениями и связанными статьями.

### 3. Ротация API ключей
Встроенная ротация между несколькими API ключами позволяет увеличить пропускную способность на бесплатных API тарифах.

### 4. Естественная генерация ответов
Ответы генерируются в стиле профессионального юридического консультанта, а не структурированных отчётов.

## API Endpoints

```bash
# Стандартный поиск
POST /api/query
{"query": "...", "max_results": 5}

# Гибридный поиск с графом
POST /api/hybrid_search
{"query": "...", "graph_enabled": true}

# Health check
GET /health/all
```

## Разработка

```bash
# Запуск тестов
pytest tests/ -v

# Запуск бенчмарка
python scripts/run_40_question_evaluation.py

# Проверка кода
ruff check .
mypy core/
```

## Лицензия

MIT License — см. [LICENSE](LICENSE) для деталей.

## Благодарности

- [LangGraph](https://langchain-ai.github.io/langgraph/) — фреймворк агентных workflow
- [ChromaDB](https://www.trychroma.com/) — векторное хранилище
- [sentence-transformers](https://www.sbert.net/) — BGE Reranker
