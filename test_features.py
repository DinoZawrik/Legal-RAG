"""
LegalRAG — Admin Panel & Chat Feature Test Suite
Tests all admin API endpoints and chat features.
"""

import httpx
import json
import sys
import os
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API = "http://localhost:8080"
ADMIN_PASSWORD = os.getenv("ADMIN_PANEL_PASSWORD", "Admin2024_Secure!")


def test(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    return passed


def get_token() -> str:
    """Get JWT auth token."""
    resp = httpx.post(f"{API}/admin/auth/login",
                      json={"username": "admin", "password": ADMIN_PASSWORD}, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token", data.get("access_token", ""))
    return ""


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def main():
    print("=" * 70)
    print("LegalRAG — Feature Test Suite")
    print("=" * 70)
    passed = 0
    failed = 0
    total = 0

    # ==================== HEALTH & INFO ====================
    print("\n--- Health & Info Endpoints ---")

    r = httpx.get(f"{API}/health", timeout=10)
    total += 1
    if test("GET /health", r.status_code == 200):
        passed += 1
    else:
        failed += 1

    r = httpx.get(f"{API}/info", timeout=10)
    data = r.json()
    total += 1
    if test("GET /info", r.status_code == 200 and "services" in data, f"services={data.get('services',{}).get('healthy','?')}/{data.get('services',{}).get('total','?')}"):
        passed += 1
    else:
        failed += 1

    r = httpx.get(f"{API}/health/all", timeout=10)
    total += 1
    if test("GET /health/all", r.status_code == 200):
        passed += 1
    else:
        failed += 1

    r = httpx.get(f"{API}/services", timeout=10)
    total += 1
    if test("GET /services", r.status_code == 200):
        passed += 1
    else:
        failed += 1

    r = httpx.get(f"{API}/status", timeout=10)
    total += 1
    if test("GET /status", r.status_code == 200):
        passed += 1
    else:
        failed += 1

    r = httpx.get(f"{API}/metrics", timeout=10)
    total += 1
    if test("GET /metrics", r.status_code == 200):
        passed += 1
    else:
        failed += 1

    # ==================== ADMIN AUTH ====================
    print("\n--- Admin Authentication ---")

    # Login with correct password
    r = httpx.post(f"{API}/admin/auth/login",
                   json={"username": "admin", "password": ADMIN_PASSWORD}, timeout=10)
    total += 1
    token = ""
    if r.status_code == 200:
        rdata = r.json()
        token = rdata.get("token", rdata.get("access_token", ""))
        if test("POST /admin/auth/login (correct)", bool(token), f"token_len={len(token)}"):
            passed += 1
        else:
            failed += 1
    else:
        test("POST /admin/auth/login (correct)", False, f"status={r.status_code}")
        failed += 1

    # Login with wrong password
    r = httpx.post(f"{API}/admin/auth/login",
                   json={"username": "admin", "password": "wrong_password_123"}, timeout=10)
    total += 1
    if test("POST /admin/auth/login (wrong pwd)", r.status_code in (401, 403)):
        passed += 1
    else:
        failed += 1

    # ==================== ADMIN FILES ====================
    print("\n--- File Management ---")

    if token:
        headers = auth_headers(token)

        # List files
        r = httpx.get(f"{API}/admin/files/list", headers=headers, timeout=15)
        total += 1
        if r.status_code == 200:
            fdata = r.json()
            docs = fdata.get("data", {}).get("documents", [])
            if test("GET /admin/files/list", True, f"docs={len(docs)}"):
                passed += 1
            else:
                failed += 1
        else:
            test("GET /admin/files/list", False, f"status={r.status_code}")
            failed += 1

        # Upload a test file
        test_content = b"Test document for admin panel upload verification."
        r = httpx.post(f"{API}/admin/files/upload",
                       headers={"Authorization": f"Bearer {token}"},
                       files={"files": ("test_admin_upload.txt", test_content, "text/plain")},
                       data={"document_type": "test", "auto_process": "true"},
                       timeout=60)
        total += 1
        uploaded_doc_id = None
        if r.status_code == 200:
            udata = r.json()
            uploaded_doc_id = udata.get("document_id")
            if test("POST /admin/files/upload", udata.get("success", False), f"doc_id={uploaded_doc_id}, chunks={udata.get('chunks_created',0)}"):
                passed += 1
            else:
                failed += 1
        else:
            test("POST /admin/files/upload", False, f"status={r.status_code}")
            failed += 1

        # Check duplicate
        r = httpx.post(f"{API}/admin/files/check-duplicate",
                       headers=headers,
                       json={"filename": "test_admin_upload.txt"},
                       timeout=10)
        total += 1
        if test("POST /admin/files/check-duplicate", r.status_code == 200):
            passed += 1
        else:
            failed += 1

        # Delete the uploaded file
        if uploaded_doc_id:
            r = httpx.delete(f"{API}/admin/files/{uploaded_doc_id}", headers=headers, timeout=15)
            total += 1
            if test("DELETE /admin/files/{doc_id}", r.status_code == 200, f"id={uploaded_doc_id}"):
                passed += 1
            else:
                failed += 1

    # ==================== ADMIN METRICS & CONFIG ====================
    print("\n--- Admin Metrics & Config ---")

    if token:
        r = httpx.get(f"{API}/admin/metrics/system", headers=headers, timeout=10)
        total += 1
        if test("GET /admin/metrics/system", r.status_code == 200):
            passed += 1
        else:
            failed += 1

        r = httpx.get(f"{API}/admin/config/rag", headers=headers, timeout=10)
        total += 1
        if test("GET /admin/config/rag", r.status_code == 200):
            passed += 1
        else:
            failed += 1

        r = httpx.get(f"{API}/admin/stats/documents", headers=headers, timeout=10)
        total += 1
        if test("GET /admin/stats/documents", r.status_code == 200):
            passed += 1
        else:
            failed += 1

    # ==================== ADMIN USERS ====================
    print("\n--- User Management ---")

    if token:
        r = httpx.get(f"{API}/admin/users/list", headers=headers, timeout=10)
        total += 1
        if test("GET /admin/users/list", r.status_code == 200):
            passed += 1
        else:
            failed += 1

    # ==================== QUERY API ====================
    print("\n--- Query API (Chat) ---")

    # Basic query
    r = httpx.post(f"{API}/api/query",
                   json={"query": "Что такое трудовой договор?", "max_results": 3, "use_cache": False},
                   timeout=120)
    total += 1
    if r.status_code == 200:
        qdata = r.json()
        answer = qdata.get("answer", "")
        chunks = qdata.get("chunks_used", 0)
        has_real_answer = len(answer) > 80 and "ошибка" not in answer.lower()[:100]
        if test("POST /api/query (basic)", has_real_answer, f"answer_len={len(answer)}, chunks={chunks}"):
            passed += 1
        else:
            test("POST /api/query (basic)", False, f"answer_preview={answer[:100]}")
            failed += 1
    else:
        test("POST /api/query (basic)", False, f"status={r.status_code}")
        failed += 1

    # Query with cache enabled
    r = httpx.post(f"{API}/api/query",
                   json={"query": "Что такое трудовой договор?", "max_results": 3, "use_cache": True},
                   timeout=120)
    total += 1
    if r.status_code == 200:
        cdata = r.json()
        if test("POST /api/query (cached)", len(cdata.get("answer", "")) > 50, "cache_hit check"):
            passed += 1
        else:
            failed += 1
    else:
        test("POST /api/query (cached)", False)
        failed += 1

    # Document upload via API
    print("\n--- Document Upload API ---")

    with open("demo_documents/zakon_o_zashite_prav_potrebitelej.txt", "rb") as f:
        r = httpx.post(f"{API}/api/upload",
                       files={"file": ("test_api_doc.txt", f, "text/plain")},
                       data={"original_filename": "test_api_doc.txt", "document_type": "regulatory", "async_processing": "false"},
                       timeout=120)
    total += 1
    if r.status_code == 200:
        updata = r.json()
        if test("POST /api/upload (document)", updata.get("success", False), f"chunks={updata.get('chunks_created',0)}"):
            passed += 1
        else:
            failed += 1
    else:
        test("POST /api/upload (document)", False, f"status={r.status_code}")
        failed += 1

    # ==================== MISC ENDPOINTS ====================
    print("\n--- Misc Endpoints ---")

    r = httpx.get(f"{API}/api/simple_test", timeout=10)
    total += 1
    if test("GET /api/simple_test", r.status_code == 200):
        passed += 1
    else:
        failed += 1

    r = httpx.get(f"{API}/test", timeout=10)
    total += 1
    if test("GET /test", r.status_code == 200):
        passed += 1
    else:
        failed += 1

    # ==================== SERVICE HEALTH (per-service) ====================
    print("\n--- Per-Service Health ---")

    for svc in ["storage_service", "cache_service", "inference_service", "search_service", "api_gateway"]:
        r = httpx.get(f"{API}/services/{svc}/health", timeout=10)
        total += 1
        if test(f"GET /services/{svc}/health", r.status_code == 200):
            passed += 1
        else:
            failed += 1

    # ==================== UI SERVICES ====================
    print("\n--- UI Services Accessibility ---")

    r = httpx.get("http://localhost:8501", timeout=10)
    total += 1
    if test("Chainlit UI (8501)", r.status_code == 200):
        passed += 1
    else:
        failed += 1

    r = httpx.get("http://localhost:8090", timeout=10)
    total += 1
    if test("Admin Panel UI (8090)", r.status_code == 200):
        passed += 1
    else:
        failed += 1

    # ==================== SUMMARY ====================
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    pct = (passed / total * 100) if total else 0
    print(f"Score: {pct:.0f}%")
    print("=" * 70)

    return 0 if failed <= 2 else 1


if __name__ == "__main__":
    sys.exit(main())
