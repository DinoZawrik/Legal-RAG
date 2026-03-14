"""Documents & Analytics page — replaces Task Monitor."""

import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st
import requests

logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080")


def _api_get(path: str, headers: Optional[Dict] = None, timeout: int = 8) -> Optional[Dict[str, Any]]:
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"API {path} returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"API {path} error: {e}")
    return None


_DOCUMENT_NAME_MAP = {
    "grazhdanskij_kodeks_rf.pdf": "Гражданский кодекс РФ",
    "grazhdanskij_kodeks_rf.txt": "Гражданский кодекс РФ",
    "semejnyj_kodeks_rf.pdf": "Семейный кодекс РФ",
    "semejnyj_kodeks_rf.txt": "Семейный кодекс РФ",
    "skodeksrf.pdf": "Семейный кодекс РФ",
    "labor_code_excerpt.txt": "Трудовой кодекс РФ (выдержка)",
    "trudovoj_kodeks_rf.pdf": "Трудовой кодекс РФ",
    "zakon_o_zashite_prav_potrebitelej.txt": "Закон о защите прав потребителей",
    "zhilishchnyj_kodeks_rf.pdf": "Жилищный кодекс РФ",
    "zhilishchnyj_kodeks_rf.txt": "Жилищный кодекс РФ",
    "test_admin_upload.txt": "Тестовый документ (admin)",
    "test_smoke.txt": "Тестовый документ (smoke)",
}


def _human_doc_name(filename: str) -> str:
    if not filename:
        return "Без названия"
    if filename in _DOCUMENT_NAME_MAP:
        return _DOCUMENT_NAME_MAP[filename]
    for key, val in _DOCUMENT_NAME_MAP.items():
        if key.lower() == filename.lower():
            return val
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    return name.replace('_', ' ').title()


def _auth_headers() -> Dict[str, str]:
    token = getattr(st.session_state, "auth_token", None)
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def render_documents_analytics():
    """Main entry point for Documents & Analytics page."""

    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #0c1929 0%, #1d4ed8 100%);
        padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem; color: white;
    ">
        <h2 style="margin:0; font-size:1.4rem; font-weight:700;">Документы и аналитика</h2>
        <p style="margin:0.3rem 0 0; opacity:0.75; font-size:0.85rem;">
        Статистика коллекции документов и конфигурация RAG-пайплайна
        </p>
    </div>
    """, unsafe_allow_html=True)

    hdrs = _auth_headers()

    # ── Row 1: Document Stats ──────────────────────────────────────
    st.subheader("Статистика документов")

    doc_stats = _api_get("/admin/stats/documents", hdrs)
    # Also fetch file list for fallback stats
    files_for_stats = _api_get("/admin/files/list?limit=200&offset=0", hdrs)

    data = {}
    if doc_stats:
        data = doc_stats.get("data", doc_stats)

    # Fallback: compute stats from file list if stats endpoint returned zeros
    if files_for_stats and files_for_stats.get("success"):
        fdata = files_for_stats.get("data", {})
        docs_list = fdata.get("documents", [])
        if docs_list and data.get("documents_count", 0) == 0:
            data["documents_count"] = fdata.get("total", len(docs_list))
            data["total_size_mb"] = sum(d.get("file_size", 0) for d in docs_list) / (1024 * 1024)

    if data:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _stat_card("Документов", data.get("documents_count", 0), "#1d4ed8")
        with c2:
            _stat_card("Чанков", data.get("chunks_count", "—"), "#7c3aed")
        with c3:
            size_mb = data.get("total_size_mb", 0)
            _stat_card("Общий размер", f"{size_mb:.1f} МБ", "#059669")
        with c4:
            recent = data.get("recent_uploads", "—")
            _stat_card("Загрузки (24ч)", recent, "#d97706")
    else:
        st.warning("Не удалось получить статистику документов")

    st.markdown("---")

    # ── Row 2: Document list ───────────────────────────────────────
    st.subheader("Загруженные документы")

    col_search, col_btn = st.columns([4, 1])
    with col_search:
        search_q = st.text_input(
            "Поиск", placeholder="Название документа...", label_visibility="collapsed",
        )
    with col_btn:
        st.button("Обновить", key="docs_refresh", use_container_width=True)

    params = {"limit": 50, "offset": 0}
    if search_q:
        params["search"] = search_q

    files_resp = _api_get(f"/admin/files/list?limit={params['limit']}&offset={params['offset']}"
                          + (f"&search={search_q}" if search_q else ""), hdrs)

    if files_resp and files_resp.get("success"):
        docs = files_resp.get("data", {}).get("documents", [])
        total = files_resp.get("data", {}).get("total", len(docs))

        if docs:
            st.caption(f"Показано {len(docs)} из {total}")

            # Table header
            h1, h2, h3, h4 = st.columns([4, 1.5, 1.5, 1])
            h1.markdown("**Документ**")
            h2.markdown("**Размер**")
            h3.markdown("**Статус**")
            h4.markdown("**Чанки**")

            for doc in docs:
                c1, c2, c3, c4 = st.columns([4, 1.5, 1.5, 1])
                with c1:
                    raw_name = doc.get("filename", "N/A")
                    st.write(f"📄 {_human_doc_name(raw_name)}")
                with c2:
                    sz = doc.get("file_size", 0)
                    if sz > 1024 * 1024:
                        st.write(f"{sz / (1024*1024):.1f} МБ")
                    elif sz > 1024:
                        st.write(f"{sz / 1024:.0f} КБ")
                    else:
                        st.write(f"{sz} Б")
                with c3:
                    status = doc.get("status", "unknown")
                    color = {"processed": "#10b981", "completed": "#10b981", "processing": "#3b82f6"}.get(status, "#94a3b8")
                    st.markdown(f'<span style="color:{color};font-weight:600;">{status}</span>',
                                unsafe_allow_html=True)
                with c4:
                    st.write(doc.get("chunks_count", "—"))
        else:
            st.info("Документов нет")
    else:
        st.info("Не удалось загрузить список документов")

    st.markdown("---")

    # ── Row 3: RAG Configuration ───────────────────────────────────
    st.subheader("RAG конфигурация")

    rag_cfg = _api_get("/admin/config/rag", hdrs)

    if rag_cfg:
        current_name = rag_cfg.get("current_config", "default")

        configs = rag_cfg.get("configs", {})
        if configs:
            config_names = list(configs.keys())
            st.info(f"Активная конфигурация: **{current_name}**")

            selected = st.selectbox("Просмотр конфигурации", config_names,
                                    index=config_names.index(current_name) if current_name in config_names else 0)
            cfg = configs.get(selected, {})

            if cfg:
                # Display key parameters as cards
                pc1, pc2, pc3 = st.columns(3)
                with pc1:
                    st.markdown("**Поиск**")
                    search_cfg = cfg.get("search", cfg)
                    st.markdown(f"- Top-K: `{search_cfg.get('top_k', 'N/A')}`")
                    st.markdown(f"- BM25 weight: `{search_cfg.get('bm25_weight', 'N/A')}`")
                    st.markdown(f"- Semantic weight: `{search_cfg.get('semantic_weight', 'N/A')}`")
                    st.markdown(f"- Reranker: `{search_cfg.get('use_reranker', 'N/A')}`")

                with pc2:
                    st.markdown("**Генерация**")
                    gen_cfg = cfg.get("generation", cfg)
                    st.markdown(f"- Model: `{gen_cfg.get('model', 'N/A')}`")
                    st.markdown(f"- Temperature: `{gen_cfg.get('temperature', 'N/A')}`")
                    st.markdown(f"- Max tokens: `{gen_cfg.get('max_tokens', 'N/A')}`")

                with pc3:
                    st.markdown("**Пайплайн**")
                    pipe_cfg = cfg.get("pipeline", cfg)
                    st.markdown(f"- Cache: `{pipe_cfg.get('use_cache', 'N/A')}`")
                    st.markdown(f"- Graph search: `{pipe_cfg.get('use_graph', 'N/A')}`")
                    st.markdown(f"- Verification: `{pipe_cfg.get('verify_answer', 'N/A')}`")

                with st.expander("Полный JSON конфигурации"):
                    st.json(cfg)
        else:
            st.info("Конфигурации не найдены")
    else:
        # Fallback: try reading local rag_configs.json
        try:
            cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "rag_configs.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    local_cfg = json.load(f)
                st.info("Загружено из локального файла rag_configs.json")
                with st.expander("Конфигурация RAG"):
                    st.json(local_cfg)
            else:
                st.info("RAG конфигурация недоступна")
        except Exception:
            st.info("RAG конфигурация недоступна")

    # Footer
    st.markdown(f"""
    <div style="text-align:right; color:#94a3b8; font-size:0.75rem; margin-top:1.5rem;">
    Обновлено: {datetime.now().strftime('%H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)


def _stat_card(title: str, value, color: str):
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {color}10, {color}05);
        border-left: 4px solid {color};
        border-radius: 10px;
        padding: 1.1rem;
    ">
        <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase; letter-spacing:0.04em;">{title}</div>
        <div style="font-size:1.6rem; font-weight:700; color:{color}; margin:0.2rem 0;">{value}</div>
    </div>
    """, unsafe_allow_html=True)
