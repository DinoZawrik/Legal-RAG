# 🏛️ LegalRAG — Legal Document Analysis System

<p align="center">
  <strong>🇬🇧 English</strong> |
  <a href="README.ru.md">🇷🇺 Русский</a>
</p>

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](https://docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agentic-purple.svg)](https://langchain-ai.github.io/langgraph/)

> Production-ready RAG system for legal document analysis with hybrid search, graph knowledge base, and agentic workflows.

## ✨ Key Features

- **Hybrid BM25 + Semantic Search** - 60/40 weighted combination for optimal retrieval on legal terminology
- **LangGraph Agentic Workflow** - 5-node CRAG-inspired architecture with self-critique and automatic fallback
- **Neo4j Graph RAG** - 95+ legal definitions with relationship traversal for enhanced context
- **Multi-Source Fallback Chain** - Vector DB -> Graph DB -> Web Search automatic fallback
- **BGE Reranker v2-m3** - Cross-encoder reranking for improved precision
- **Microservices Architecture** - 5 independent services with health monitoring and graceful shutdown
- **Telegram Bot + Admin Panel** - Full-featured user interface with JWT authentication

## 🏗️ Architecture

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
   Hybrid BM25      LLM Quality       Query Reform        Gemini Flash      Self-Check
   + Graph Lookup    Assessment       + Web Search        Generation        Validation
```

## 🛠️ Tech Stack

| Category | Technology |
|----------|------------|
| **LLM** | Google Gemini 2.5 Flash / OpenAI GPT-4 |
| **Embeddings** | Gemini text-embedding-004 (768-dim) |
| **Vector DB** | ChromaDB with async client |
| **Graph DB** | Neo4j 5.x with APOC |
| **Relational DB** | PostgreSQL 16 |
| **Cache** | Redis 7 |
| **Framework** | FastAPI + LangGraph + Aiogram |
| **Reranker** | BGE Reranker v2-m3 (sentence-transformers) |

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Gemini API Key (free tier available)

### 1. Clone and Setup

```bash
git clone https://github.com/YOUR_USERNAME/legal-rag-system.git
cd legal-rag-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys:
#   GEMINI_API_KEY=your_key_here
#   TELEGRAM_BOT_TOKEN=your_token_here
```

### 3. Start Infrastructure

```bash
# Start PostgreSQL, Redis, ChromaDB
docker-compose up -d

# Start Neo4j (optional, for graph-enhanced search)
docker-compose -f docker-compose.neo4j.yml up -d
```

### 4. Load Data and Run

```bash
# Load documents into vector store
python simple_chromadb_load.py

# Start microservices
python start_microservices.py
```

### 5. Verify

```bash
# Health check
curl http://localhost:8080/health/all

# Test query
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is a concession agreement?", "max_results": 5}'
```

## 📊 Performance

| Metric | Value |
|--------|-------|
| Accuracy (40-question benchmark) | **97.5%** |
| Average response time | ~33 sec |
| API throughput | 1500 RPD (with key rotation) |
| Cache hit rate | 67% on similar queries |

## 📁 Project Structure

```
legal-rag-system/
├── core/                    # Core modules
│   ├── hybrid_bm25_search.py    # Primary search engine
│   ├── langgraph_rag_workflow.py # Agentic RAG workflow
│   ├── reranker.py              # BGE Reranker
│   └── settings.py              # Configuration
├── services/                # Microservices
│   ├── gateway/                 # API Gateway
│   ├── search_service_core.py   # Search orchestration
│   └── inference_service.py     # LLM inference
├── bot/                     # Telegram bot
├── admin_panel/             # Streamlit admin UI
├── tools/                   # RAG tools (graph, web)
├── docker-compose.yml       # Infrastructure
└── start_microservices.py   # Entry point
```

## 💡 Key Innovations

### 1. Hybrid Search for Legal Text
BM25 keyword matching (60%) combined with semantic embeddings (40%) solves the problem of poor embedding quality on Russian legal terminology.

### 2. Graph-Enhanced Fallback
When vector search quality is insufficient, the system automatically queries Neo4j graph database for definitions and related articles.

### 3. API Key Rotation
Built-in rotation across multiple API keys enables higher throughput on free API tiers.

### 4. Natural Answer Generation
Answers are generated in the style of a professional legal consultant, not structured reports.

## 📡 API Endpoints

```bash
# Standard search
POST /api/query
{"query": "...", "max_results": 5}

# Hybrid search with graph
POST /api/hybrid_search
{"query": "...", "graph_enabled": true}

# Health check
GET /health/all
```

## 🔧 Development

```bash
# Run tests
pytest tests/ -v

# Run benchmark
python test_40_natural_answers.py

# Code quality
ruff check .
mypy core/
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [LangGraph](https://langchain-ai.github.io/langgraph/) for agentic workflow framework
- [ChromaDB](https://www.trychroma.com/) for vector storage
- [sentence-transformers](https://www.sbert.net/) for BGE Reranker
