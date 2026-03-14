"""Dashboard component — system overview with real-time metrics."""

from __future__ import annotations

import os
import time
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import streamlit as st
import requests

logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080")


def _api_get(path: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """Safe API GET request."""
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def render_dashboard():
    """Render the main dashboard page."""

    st.markdown("""
    <div style="
    background: linear-gradient(135deg, #0c1929 0%, #1d4ed8 100%);
    padding: 2rem 2.5rem;
    border-radius: 12px;
    margin-bottom: 2rem;
    color: white;
    position: relative;
    overflow: hidden;
    ">
    <div style="position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(circle at 30% 50%,rgba(212,168,83,0.06) 0%,transparent 50%);pointer-events:none;"></div>
    <h1 style="margin:0; font-size:1.8rem; font-weight:700; letter-spacing:0.02em;">Dashboard</h1>
    <p style="margin:0.4rem 0 0 0; opacity:0.8; font-size:0.9rem; letter-spacing:0.01em;">
    LegalRAG — AI-система анализа российских нормативных документов
    </p>
    </div>
    """, unsafe_allow_html=True)

    # Status Row
    info = _api_get("/info")
    health = _api_get("/health")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        _metric_card(
            "API Gateway",
            "Online" if info else "Offline",
            "v" + info.get("version", "?") if info else "--",
            ok=info is not None,
        )

    with col2:
        services = info.get("services", {}) if info else {}
        total = services.get("total", 0)
        healthy = services.get("healthy", 0)
        _metric_card(
            "Микросервисы",
            f"{healthy}/{total}",
            "все здоровы" if healthy == total and total > 0 else "есть проблемы",
            ok=healthy == total and total > 0,
        )

    with col3:
        # Check databases
        pg_ok = _check_port(5432)
        redis_ok = _check_port(6379)
        chroma_ok = _check_port(8000)
        neo4j_ok = _check_port(7687)
        db_count = sum([pg_ok, redis_ok, chroma_ok, neo4j_ok])
        _metric_card(
            "Базы данных",
            f"{db_count}/4",
            "PG / Redis / Chroma / Neo4j",
            ok=db_count == 4,
        )

    with col4:
        _metric_card(
            "Chat UI",
            "Online" if _check_port(8501) else "Offline",
            "Chainlit :8501",
            ok=_check_port(8501),
        )

    st.markdown("---")

    # Architecture Overview
    st.subheader("Архитектура системы")

    st.markdown("""
    ```mermaid
    graph TB
    subgraph " Clients"
    A[Chainlit Chat UI<br/>:8501] --> GW
    B[Telegram Bot] --> GW
    C[Admin Panel<br/>:8090] --> GW
    end
    
    subgraph " API Gateway :8080"
    GW[FastAPI Gateway<br/>Rate Limiting · JWT Auth]
    end
    
    subgraph " Microservices"
    GW --> SS[Search Service<br/>Hybrid BM25 + Semantic]
    GW --> IS[Inference Service<br/>Gemini 2.5 Flash]
    GW --> ST[Storage Service<br/>Multi-DB]
    GW --> CS[Cache Service<br/>Redis + In-Memory]
    end
    
    subgraph " Data Layer"
    SS --> PG[(PostgreSQL 16<br/>Metadata + pgvector)]
    SS --> CH[(ChromaDB<br/>Vector Embeddings)]
    SS --> N4[(Neo4j 5.15<br/>Knowledge Graph)]
    CS --> RD[(Redis 7<br/>Cache + Sessions)]
    end
    ```
    """)

    # Database Details
    st.subheader("Состояние баз данных")

    db_col1, db_col2, db_col3, db_col4 = st.columns(4)

    with db_col1:
        _db_status_card("PostgreSQL 16", "localhost:5432", pg_ok, "Метаданные, пользователи, чанки")
    with db_col2:
        _db_status_card("ChromaDB", "localhost:8000", chroma_ok, "Векторные эмбеддинги (768-dim)")
    with db_col3:
        _db_status_card("Neo4j 5.15", "localhost:7687", neo4j_ok, "Граф знаний (95+ определений)")
    with db_col4:
        _db_status_card("Redis 7", "localhost:6379", redis_ok, "Кэш, сессии, FSM")

    st.markdown("---")

    # RAG Pipeline
    st.subheader("RAG Pipeline (CRAG Architecture)")

    pipeline_cols = st.columns(5)
    steps = [
        ("1", "Поиск", "Hybrid BM25 + Semantic + Graph"),
        ("2", "Оценка", "Document Grading (LLM)"),
        ("3", "Ремонт", "Query Reformulation + Web"),
        ("4", "Генерация", "Gemini 3 Flash + Nemotron"),
        ("5", "Критика", "Self-check + Verification"),
    ]
    for col, (icon, title, desc) in zip(pipeline_cols, steps):
        with col:
            st.markdown(f"""
            <div style="
            background: linear-gradient(135deg, #f8fafc, #f1f5f9);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 1.2rem;
            text-align: center;
            min-height: 110px;
            ">
            <div style="font-size: 1.5rem; font-weight: 700; color: #1d4ed8;">{icon}</div>
            <div style="font-weight: 600; color: #0c1929; margin: 0.3rem 0; font-size: 0.9rem;">{title}</div>
            <div style="font-size: 0.75rem; color: #64748b;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Tech Stack
    st.subheader("Technology Stack")

    tech_col1, tech_col2, tech_col3 = st.columns(3)

    with tech_col1:
        st.markdown("""
        **AI / ML**
        - LLM: Gemini 3 Flash / Nemotron 120B
        - Embeddings: text-embedding-004 (768-dim)
        - Reranker: BGE Reranker v2-m3
        - Framework: LangGraph + LangChain
        """)

    with tech_col2:
        st.markdown("""
        **Backend**
        - API: FastAPI + Uvicorn
        - Bot: Aiogram 3.0+
        - Auth: JWT (PyJWT)
        - Orchestration: Custom Microservices
        """)

    with tech_col3:
        st.markdown("""
        **Data**
        - Vector: ChromaDB + pgvector
        - Graph: Neo4j 5.15 (APOC)
        - Relational: PostgreSQL 16
        - Cache: Redis 7
        """)

    # Performance Metrics
    st.subheader("Метрики производительности")

    perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)

    with perf_col1:
        st.metric("Точность (40Q Benchmark)", "97.5%", "+2.5%")
    with perf_col2:
        st.metric("Среднее время ответа", "~33с", "-5с")
    with perf_col3:
        st.metric("Cache Hit Rate", "67%", "+12%")
    with perf_col4:
        st.metric("API Throughput", "1500 RPD", "")

    st.markdown(f"""
    <div style="text-align: center; color: #94a3b8; margin-top: 2rem; font-size: 0.8rem; letter-spacing: 0.02em;">
    LegalRAG v5.0 -- Gemini 3 Flash + Nemotron 120B -- {datetime.now().strftime('%Y-%m-%d %H:%M')}
    </div>
    """, unsafe_allow_html=True)


# Helper Components

def _metric_card(title: str, value: str, subtitle: str, ok: bool = True):
    color = "#10b981" if ok else "#ef4444"
    bg = "#f0fdf4" if ok else "#fef2f2"
    border = "#10b981" if ok else "#ef4444"
    st.markdown(f"""
    <div style="
    background: {bg};
    border: 1px solid rgba(0,0,0,0.04);
    border-left: 4px solid {border};
    border-radius: 12px;
    padding: 1.2rem;
    ">
    <div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 500;">{title}</div>
    <div style="font-size: 1.6rem; font-weight: 700; color: {color}; margin: 0.3rem 0;">{value}</div>
    <div style="font-size: 0.75rem; color: #94a3b8;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def _db_status_card(name: str, endpoint: str, is_ok: bool, description: str):
    color = "#10b981" if is_ok else "#ef4444"
    bg = "#f0fdf4" if is_ok else "#fef2f2"
    status_text = "Online" if is_ok else "Offline"
    st.markdown(f"""
    <div style="
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
    ">
    <div style="font-weight: 600; font-size: 0.95rem; color: #0c1929; margin-bottom: 0.3rem;">{name}</div>
    <div style="font-size: 0.8rem; color: {color}; font-weight: 500; margin-bottom: 0.3rem;">{status_text} -- {endpoint}</div>
    <div style="font-size: 0.72rem; color: #94a3b8;">{description}</div>
    </div>
    """, unsafe_allow_html=True)


def _check_port(port: int, host: str = "localhost", timeout: float = 1.5) -> bool:
    """Check if a TCP port is open."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
        return True
    except Exception:
        return False
