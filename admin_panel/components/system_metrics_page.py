"""System Metrics page — replaces Telegram user management."""

import os
import time
import socket
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import streamlit as st
import requests

logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080")


def _api_get(path: str, headers: Optional[Dict] = None, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """Safe API GET with optional auth headers."""
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def _auth_headers() -> Dict[str, str]:
    token = getattr(st.session_state, "auth_token", None)
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _check_port(port: int) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=1):
            return True
    except OSError:
        return False


def render_system_metrics():
    """Main entry point for the System Metrics page."""

    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #0c1929 0%, #1d4ed8 100%);
        padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem; color: white;
    ">
        <h2 style="margin:0; font-size:1.4rem; font-weight:700;">Системные метрики</h2>
        <p style="margin:0.3rem 0 0; opacity:0.75; font-size:0.85rem;">
        Мониторинг здоровья сервисов, баз данных и производительности API Gateway
        </p>
    </div>
    """, unsafe_allow_html=True)

    hdrs = _auth_headers()

    # ── Row 1: Service health ──────────────────────────────────────
    st.subheader("Здоровье сервисов")

    services_info = _api_get("/info", hdrs)
    services_map: Dict[str, Any] = {}
    if services_info:
        for s in services_info.get("services_detail", services_info.get("services", {}).get("list", [])):
            name = s if isinstance(s, str) else s.get("name", "unknown")
            services_map[name] = s

    # Per-service cards via /services/{name}/health
    service_names = ["search", "inference", "storage", "cache", "graph"]
    cols = st.columns(len(service_names))

    for col, svc in zip(cols, service_names):
        health = _api_get(f"/services/{svc}/health", hdrs)
        with col:
            if health:
                status = health.get("status", "unknown")
                ok = status in ("healthy", "running")
                color = "#10b981" if ok else "#ef4444"
                bg = "#f0fdf4" if ok else "#fef2f2"
                metrics = health.get("metrics", {})
                reqs = metrics.get("request_count", 0)
                errs = metrics.get("error_count", 0)
                uptime = metrics.get("uptime_seconds", 0)
                uptime_str = f"{int(uptime // 3600)}ч {int((uptime % 3600) // 60)}м" if uptime else "--"
            else:
                ok = False
                color = "#ef4444"
                bg = "#fef2f2"
                status = "offline"
                reqs = errs = 0
                uptime_str = "--"

            st.markdown(f"""
            <div style="background:{bg}; border-left:4px solid {color}; border-radius:10px; padding:1rem;">
                <div style="font-weight:700; color:#0c1929; font-size:0.95rem; text-transform:capitalize;">{svc}</div>
                <div style="color:{color}; font-weight:600; font-size:0.8rem; margin:0.2rem 0;">{status.upper()}</div>
                <div style="font-size:0.75rem; color:#64748b;">Запросы: {reqs}</div>
                <div style="font-size:0.75rem; color:#64748b;">Ошибки: {errs}</div>
                <div style="font-size:0.75rem; color:#64748b;">Uptime: {uptime_str}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Row 2: Infrastructure ──────────────────────────────────────
    st.subheader("Инфраструктура")

    infra = [
        ("PostgreSQL", 5432, "Метаданные и чанки"),
        ("Redis", 6379, "Кэш и сессии"),
        ("ChromaDB", 8000, "Векторные эмбеддинги"),
        ("Neo4j", 7687, "Граф знаний"),
    ]

    icols = st.columns(len(infra))
    for col, (name, port, desc) in zip(icols, infra):
        alive = _check_port(port)
        color = "#10b981" if alive else "#ef4444"
        bg = "#f0fdf4" if alive else "#fef2f2"
        label = "Online" if alive else "Offline"
        with col:
            st.markdown(f"""
            <div style="background:{bg}; border-left:4px solid {color}; border-radius:10px; padding:1rem;">
                <div style="font-weight:700; color:#0c1929; font-size:0.9rem;">{name}</div>
                <div style="color:{color}; font-weight:600; font-size:0.8rem;">:{port} — {label}</div>
                <div style="font-size:0.75rem; color:#94a3b8;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Row 3: Gateway Metrics ─────────────────────────────────────
    st.subheader("Метрики API Gateway")

    gw_metrics = _api_get("/admin/metrics/system", hdrs)

    if gw_metrics:
        gw = gw_metrics.get("gateway", {})
        health_summary = gw_metrics.get("health_summary", {})

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Всего запросов", gw.get("total_requests", 0))
        with m2:
            st.metric("Всего ошибок", gw.get("total_errors", 0))
        with m3:
            uptime_s = gw.get("uptime_seconds", 0)
            hrs = int(uptime_s // 3600)
            mins = int((uptime_s % 3600) // 60)
            st.metric("Uptime Gateway", f"{hrs}ч {mins}м")
        with m4:
            healthy_count = health_summary.get("healthy", 0)
            total_count = health_summary.get("total", 0)
            st.metric("Сервисы", f"{healthy_count}/{total_count} OK")

        # Per-service metrics table
        svc_metrics = gw_metrics.get("services", {})
        if svc_metrics:
            st.markdown("**Детальные метрики по сервисам**")
            rows = []
            for name, m in svc_metrics.items():
                rows.append({
                    "Сервис": name,
                    "Запросы": m.get("request_count", 0),
                    "Ошибки": m.get("error_count", 0),
                    "Ср. время (с)": round(m.get("avg_response_time", 0), 3),
                    "Ошибок (%)": round(m.get("error_rate", 0) * 100, 1),
                    "Uptime (мин)": round(m.get("uptime_seconds", 0) / 60, 1),
                })
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.warning("Не удалось получить метрики Gateway — проверьте авторизацию")

    st.markdown("---")

    # ── Row 4: System Logs ─────────────────────────────────────────
    st.subheader("Последние логи")

    logs = _api_get("/admin/logs/stream?limit=15", hdrs)
    if logs and isinstance(logs, dict):
        log_list = logs.get("logs", [])
        if log_list:
            for entry in log_list[:15]:
                lvl = entry.get("level", "INFO")
                color = {"ERROR": "#ef4444", "WARNING": "#f59e0b"}.get(lvl, "#64748b")
                ts = entry.get("timestamp", "")[:19]
                svc = entry.get("service", "")
                msg = entry.get("message", "")
                st.markdown(
                    f'<span style="color:{color};font-weight:600;font-size:0.8rem;">[{lvl}]</span> '
                    f'<span style="color:#94a3b8;font-size:0.75rem;">{ts}</span> '
                    f'<span style="color:#1d4ed8;font-size:0.8rem;">{svc}</span> '
                    f'<span style="font-size:0.8rem;">{msg}</span>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("Логи пусты")
    else:
        st.info("Логи недоступны")

    # Footer timestamp
    st.markdown(f"""
    <div style="text-align:right; color:#94a3b8; font-size:0.75rem; margin-top:1.5rem;">
    Обновлено: {datetime.now().strftime('%H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)
