#!/usr/bin/env python3
"""
Комплексное тестирование Legal-RAG: модели, поиск, инференс, API.
"""
import asyncio
import json
import os
import sys
import time
import requests

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")
GATEWAY = "http://localhost:8080"

# Цвета
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

results = []

def log_result(category, test_name, passed, detail=""):
    status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    results.append((category, test_name, passed, detail))
    trunc = (detail[:100] + "...") if len(detail) > 100 else detail
    print(f"[{status}] {test_name}: {trunc}")


#
# 1. ТЕСТИРОВАНИЕ МОДЕЛЕЙ GEMINI
#
def test_gemini_models():
    print(f"\n{BOLD}{CYAN} 1. GEMINI MODELS {RESET}")
    from google import genai

    client = genai.Client(api_key=GEMINI_KEY)
    test_prompt = "Что такое трудовой договор? Ответь в 1-2 предложениях."

    models_to_test = [
        "gemini-3-flash-preview",        # Основной инференс
        "gemini-3.1-flash-lite-preview",  # Оценка уверенности
    ]

    for model in models_to_test:
        try:
            start = time.time()
            r = client.models.generate_content(
                model=model,
                contents=test_prompt,
                config={"max_output_tokens": 200, "temperature": 0.1},
            )
            elapsed = time.time() - start
            text = r.text.strip() if r.text else ""
            has_answer = len(text) > 10 and ("договор" in text.lower() or "соглашен" in text.lower()
                or "contract" in text.lower() or "agreement" in text.lower()
                or "employ" in text.lower() or "трудов" in text.lower())
            log_result("Gemini", model, has_answer, f"{elapsed:.1f}s | {text[:80]}")
        except Exception as e:
            log_result("Gemini", model, False, str(e)[:100])
        time.sleep(3)  # rate limit - free tier needs more delay


#
# 2. ТЕСТИРОВАНИЕ МОДЕЛЕЙ OPENROUTER
#
def test_openrouter_models():
    print(f"\n{BOLD}{CYAN} 2. OPENROUTER MODELS {RESET}")
    if not OR_KEY:
        print(" [SKIP] OPENROUTER_API_KEY not set")
        return

    test_prompt = "Что такое трудовой договор? Ответь в 1-2 предложениях на русском."
    models_to_test = [
        "nvidia/nemotron-3-super-120b-a12b:free",  # CRAG генерация
    ]

    for model in models_to_test:
        try:
            start = time.time()
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": test_prompt},
                    ],
                    "max_tokens": 200,
                },
                timeout=30,
            )
            elapsed = time.time() - start
            if r.status_code == 200:
                data = r.json()
                text = data["choices"][0]["message"]["content"].strip()
                has_answer = len(text) > 10
                log_result("OpenRouter", model, has_answer, f"{elapsed:.1f}s | {text[:80]}")
            else:
                log_result("OpenRouter", model, False, f"HTTP {r.status_code}: {r.text[:80]}")
        except Exception as e:
            log_result("OpenRouter", model, False, str(e)[:100])
        time.sleep(2)


#
# 3. ТЕСТИРОВАНИЕ ПОИСКОВОГО ПАЙПЛАЙНА
#
def test_search_pipeline():
    print(f"\n{BOLD}{CYAN} 3. SEARCH PIPELINE {RESET}")

    # 3a. ChromaDB — document count
    try:
        import chromadb
        client = chromadb.HttpClient(host="localhost", port=8000)
        cols = client.list_collections()
        total = 0
        for c in cols:
            col = client.get_collection(c.name)
            cnt = col.count()
            total += cnt
        log_result("Search", "ChromaDB documents", total > 0, f"{total} documents in {len(cols)} collections")
    except Exception as e:
        log_result("Search", "ChromaDB documents", False, str(e)[:100])

    # 3b. BM25 search (via hybrid_search)
    try:
        loop = asyncio.new_event_loop()

        async def _bm25():
            import chromadb
            from core.hybrid_bm25_search import hybrid_search
            client = await chromadb.AsyncHttpClient(host="localhost", port=8000)
            col = await client.get_collection("documents")
            results = await hybrid_search(chroma_collection=col, query="трудовой договор", k=3)
            return results

        r = loop.run_until_complete(_bm25())
        loop.close()
        has_results = len(r) > 0
        top_score = r[0].get("hybrid_score", 0) if r else 0
        log_result("Search", "Hybrid BM25+Semantic", has_results, f"{len(r)} results, top_score={top_score:.3f}")
    except Exception as e:
        log_result("Search", "Hybrid BM25+Semantic", False, str(e)[:100])

    # 3c. Different queries
    test_queries = [
        ("трудовой договор", "labor contract"),
        ("защита прав потребителей", "consumer protection"),
        ("увольнение работника", "employee dismissal"),
        ("срочный трудовой договор", "fixed-term contract"),
    ]
    for query, label in test_queries:
        try:
            r = requests.post(
                f"{GATEWAY}/api/query",
                json={"query": query, "max_results": 3},
                timeout=90,
            )
            data = r.json()
            chunks = data.get("chunks_used", 0)
            log_result("Search", f"Query: {label}", chunks > 0, f"{chunks} chunks found")
        except Exception as e:
            log_result("Search", f"Query: {label}", False, str(e)[:100])


#
# 4. ТЕСТИРОВАНИЕ INFERENCE (E2E через Gateway)
#
def test_inference_e2e():
    print(f"\n{BOLD}{CYAN} 4. E2E INFERENCE {RESET}")

    queries = [
        ("Что такое трудовой договор?", "definition"),
        ("Какие бывают виды трудовых договоров?", "types"),
        ("Каков максимальный срок срочного трудового договора?", "max_term"),
        ("Что такое выходное пособие?", "severance"),
        ("Каковы права потребителя при возврате товара?", "consumer_return"),
    ]

    for query, label in queries:
        try:
            start = time.time()
            r = requests.post(
                f"{GATEWAY}/api/query",
                json={"query": query, "max_results": 5},
                timeout=90,
            )
            elapsed = time.time() - start
            data = r.json()
            success = data.get("success", False)
            answer = data.get("answer", "")
            chunks = data.get("chunks_used", 0)
            has_good_answer = (
                success
                and len(answer) > 50
                and "ошибка" not in answer.lower()
            )
            log_result(
                "Inference",
                f"E2E: {label}",
                has_good_answer,
                f"{elapsed:.1f}s | {chunks} chunks | {len(answer)} chars",
            )
        except Exception as e:
            log_result("Inference", f"E2E: {label}", False, str(e)[:100])


#
# 5. ТЕСТИРОВАНИЕ API GATEWAY
#
def test_api_gateway():
    print(f"\n{BOLD}{CYAN} 5. API GATEWAY {RESET}")

    # 5a. /info
    try:
        r = requests.get(f"{GATEWAY}/info", timeout=10)
        data = r.json()
        healthy = data.get("services", {}).get("healthy", 0)
        total = data.get("services", {}).get("total", 0)
        log_result("Gateway", "/info endpoint", healthy == total and total >= 4, f"{healthy}/{total} healthy")
    except Exception as e:
        log_result("Gateway", "/info endpoint", False, str(e)[:100])

    # 5b. /health/all
    try:
        r = requests.get(f"{GATEWAY}/health/all", timeout=10)
        log_result("Gateway", "/health/all", r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as e:
        log_result("Gateway", "/health/all", False, str(e)[:100])

    # 5c. /metrics
    try:
        r = requests.get(f"{GATEWAY}/metrics", timeout=10)
        log_result("Gateway", "/metrics", r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as e:
        log_result("Gateway", "/metrics", False, str(e)[:100])

    # 5d. /api/query with empty query
    try:
        r = requests.post(f"{GATEWAY}/api/query", json={"query": ""}, timeout=30)
        data = r.json()
        # Should handle gracefully
        log_result("Gateway", "Empty query handling", r.status_code in (200, 400, 422), f"HTTP {r.status_code}")
    except Exception as e:
        log_result("Gateway", "Empty query handling", False, str(e)[:100])


#
# 6. ТЕСТИРОВАНИЕ CHAINLIT
#
def test_chainlit():
    print(f"\n{BOLD}{CYAN} 6. CHAINLIT UI {RESET}")
    try:
        r = requests.get("http://localhost:8501", timeout=10)
        log_result("Chainlit", "Web UI accessible", r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as e:
        log_result("Chainlit", "Web UI accessible", False, str(e)[:100])


#
# 7. ТЕСТИРОВАНИЕ ADMIN PANEL
#
def test_admin_panel():
    print(f"\n{BOLD}{CYAN} 7. ADMIN PANEL {RESET}")
    try:
        r = requests.get("http://localhost:8090", timeout=10)
        log_result("Admin", "Admin panel accessible", r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as e:
        log_result("Admin", "Admin panel accessible", False, str(e)[:100])


#
# 8. ТЕСТИРОВАНИЕ DOCKER ИНФРАСТРУКТУРЫ
#
def test_infrastructure():
    print(f"\n{BOLD}{CYAN} 8. INFRASTRUCTURE {RESET}")

    services = [
        ("PostgreSQL", "localhost", 5432, None),
        ("Redis", "localhost", 6379, None),
        ("ChromaDB", "localhost", 8000, "/api/v2/heartbeat"),
        ("Neo4j", "localhost", 7474, "/"),
    ]

    for name, host, port, path in services:
        try:
            if path:
                r = requests.get(f"http://{host}:{port}{path}", timeout=5)
                log_result("Infra", f"{name} ({port})", r.status_code in (200, 301, 302), f"HTTP {r.status_code}")
            else:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((host, port))
                s.close()
                log_result("Infra", f"{name} ({port})", True, "TCP connection OK")
        except Exception as e:
            log_result("Infra", f"{name} ({port})", False, str(e)[:100])


#
# 9. ТЕСТИРОВАНИЕ EMBEDDINGS
#
def test_embeddings():
    print(f"\n{BOLD}{CYAN} 9. EMBEDDINGS {RESET}")

    loop = asyncio.new_event_loop()

    async def _test():
        from core.giga_local_embeddings_client import GigaLocalEmbeddingsClient
        client = GigaLocalEmbeddingsClient()

        # Test single text
        emb = await client.generate_embeddings(["тестовый текст"])
        return emb

    try:
        emb = loop.run_until_complete(_test())
        loop.close()
        dim = len(emb[0]) if emb else 0
        log_result("Embeddings", "Local fallback", dim > 0, f"dim={dim}")
    except Exception as e:
        log_result("Embeddings", "Local fallback", False, str(e)[:100])

    # Semantic similarity test
    loop2 = asyncio.new_event_loop()

    async def _sim():
        from core.giga_local_embeddings_client import GigaLocalEmbeddingsClient
        import numpy as np
        client = GigaLocalEmbeddingsClient()
        emb = await client.generate_embeddings([
            "трудовой договор между работодателем и работником",
            "соглашение о трудовых отношениях",
            "кулинарный рецепт торта наполеон",
        ])
        # Cosine similarity
        def cosine(a, b):
            a, b = np.array(a), np.array(b)
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

        sim_related = cosine(emb[0], emb[1])
        sim_unrelated = cosine(emb[0], emb[2])
        return sim_related, sim_unrelated

    try:
        sim_r, sim_u = loop2.run_until_complete(_sim())
        loop2.close()
        quality = sim_r > sim_u  # Related texts should be more similar
        log_result(
            "Embeddings",
            "Semantic quality",
            quality,
            f"related={sim_r:.3f} > unrelated={sim_u:.3f}",
        )
    except Exception as e:
        log_result("Embeddings", "Semantic quality", False, str(e)[:100])


#
# MAIN
#
if __name__ == "__main__":
    print(f"\n{BOLD}{'='*60}")
    print(f"LEGAL-RAG COMPREHENSIVE TEST SUITE")
    print(f"{'='*60}{RESET}\n")

    test_infrastructure()
    test_embeddings()
    test_gemini_models()
    test_openrouter_models()
    test_api_gateway()
    test_search_pipeline()
    test_inference_e2e()
    test_chainlit()
    test_admin_panel()

    # Summary
    print(f"\n{BOLD}{'='*60}")
    print(f"TEST RESULTS SUMMARY")
    print(f"{'='*60}{RESET}")

    total = len(results)
    passed = sum(1 for _, _, p, _ in results if p)
    failed = total - passed

    categories = {}
    for cat, name, p, detail in results:
        if cat not in categories:
            categories[cat] = {"pass": 0, "fail": 0}
        if p:
            categories[cat]["pass"] += 1
        else:
            categories[cat]["fail"] += 1

    for cat, counts in categories.items():
        p, f = counts["pass"], counts["fail"]
        color = GREEN if f == 0 else (YELLOW if p > f else RED)
        print(f"{color}{cat:15s}: {p}/{p+f} passed{RESET}")

    print(f"\n {BOLD}TOTAL: {passed}/{total} passed", end="")
    if failed:
        print(f" ({RED}{failed} failed{RESET}{BOLD})", end="")
    print(f"{RESET}")

    if failed:
        print(f"\n {RED}Failed tests:{RESET}")
        for cat, name, p, detail in results:
            if not p:
                print(f"{RED}[FAIL]{RESET} [{cat}] {name}: {detail}")

    print()
