"""
LegalRAG — Final Demo Readiness Check
Comprehensive verification before screencast.
"""
import httpx
import time
import sys

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

def check(name, ok, detail=""):
    icon = f"{GREEN}OK{RESET}" if ok else f"{RED}FAIL{RESET}"
    line = f"  [{icon}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok

def main():
    print(f"\n{BOLD}{'='*70}")
    print("LEGALRAG — FINAL DEMO READINESS CHECK")
    print(f"{'='*70}{RESET}\n")
    
    total = 0
    passed = 0
    
    # === INFRASTRUCTURE ===
    print(f"{BOLD}1. Infrastructure{RESET}")
    
    r = httpx.get("http://localhost:8080/health", timeout=10)
    total += 1
    if check("API Gateway (8080)", r.status_code == 200):
        passed += 1
    
    r = httpx.get("http://localhost:8501", timeout=10)
    total += 1
    if check("Chainlit Chat (8501)", r.status_code == 200):
        passed += 1
    
    r = httpx.get("http://localhost:8090", timeout=10)
    total += 1
    if check("Admin Panel (8090)", r.status_code == 200):
        passed += 1
    
    r = httpx.get("http://localhost:8080/info", timeout=10)
    data = r.json()
    svc = data.get("services", {})
    total += 1
    if check("All services healthy", svc.get("healthy") == svc.get("total"), f"{svc.get('healthy')}/{svc.get('total')} services"):
        passed += 1
    
    # === AUTH ===
    print(f"\n{BOLD}2. Authentication{RESET}")
    
    r = httpx.post("http://localhost:8080/admin/auth/login",
                   json={"username": "admin", "password": "Admin2024_Secure!"}, timeout=10)
    token = r.json().get("access_token", "") if r.status_code == 200 else ""
    total += 1
    if check("Admin login", r.status_code == 200 and bool(token)):
        passed += 1
    
    r = httpx.post("http://localhost:8080/admin/auth/login",
                   json={"username": "admin", "password": "wrong"}, timeout=10)
    total += 1
    if check("Wrong password rejected", r.status_code == 401):
        passed += 1
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # === ADMIN ENDPOINTS ===
    print(f"\n{BOLD}3. Admin Panel Endpoints{RESET}")
    
    for ep in ["/admin/files/list", "/admin/metrics/system", "/admin/config/rag",
               "/admin/stats/documents", "/admin/users/list"]:
        r = httpx.get(f"http://localhost:8080{ep}", headers=headers, timeout=15)
        total += 1
        if check(f"GET {ep}", r.status_code == 200):
            passed += 1
    
    # === CHAT ===
    print(f"\n{BOLD}4. Chat Answers{RESET}")
    
    questions = [
        ("Что такое трудовой договор?", ["договор", "работник", "работодатель"]),
        ("Какие права потребителя при недостатках товара?", ["право", "потребител", "недостат"]),
    ]
    
    for q, keywords in questions:
        start = time.time()
        r = httpx.post("http://localhost:8080/api/query",
                       json={"query": q, "max_results": 5, "use_cache": False}, timeout=120)
        elapsed = time.time() - start
        total += 1
        if r.status_code == 200:
            answer = r.json().get("answer", "")
            has_answer = len(answer) > 80 and "ошибка" not in answer.lower()[:100]
            kw_found = sum(1 for kw in keywords if kw.lower() in answer.lower())
            if check(f"Q: {q[:45]}...", has_answer, f"{elapsed:.1f}s, {len(answer)} chars, {kw_found}/{len(keywords)} keywords"):
                passed += 1
        else:
            check(f"Q: {q[:45]}...", False, f"HTTP {r.status_code}")
    
    # === UPLOAD ===
    print(f"\n{BOLD}5. Document Upload{RESET}")
    
    r = httpx.post("http://localhost:8080/api/upload",
                   files={"file": ("readiness_test.txt", b"Test doc for demo readiness check.", "text/plain")},
                   data={"original_filename": "readiness_test.txt", "document_type": "regulatory", "async_processing": "false"},
                   timeout=60)
    total += 1
    if r.status_code == 200:
        udata = r.json()
        if check("Document upload", udata.get("success", False), f"chunks={udata.get('chunks_created',0)}"):
            passed += 1
    else:
        check("Document upload", False, f"HTTP {r.status_code}")
    
    # === PER-SERVICE HEALTH ===
    print(f"\n{BOLD}6. Per-Service Health{RESET}")
    
    for svc in ['storage_service', 'cache_service', 'inference_service', 'search_service', 'api_gateway']:
        r = httpx.get(f"http://localhost:8080/services/{svc}/health", timeout=10)
        total += 1
        if check(svc, r.status_code == 200):
            passed += 1
    
    # === SUMMARY ===
    pct = (passed / total * 100) if total else 0
    color = GREEN if pct == 100 else YELLOW if pct >= 80 else RED
    
    print(f"\n{BOLD}{'='*70}")
    print(f"DEMO READINESS: {color}{passed}/{total} ({pct:.0f}%){RESET}")
    
    if pct == 100:
        print(f"{GREEN}{BOLD}ALL SYSTEMS GO — Ready for screencast!{RESET}")
    elif pct >= 80:
        print(f"{YELLOW}MOSTLY READY — some issues to address{RESET}")
    else:
        print(f"{RED}NOT READY — critical issues found{RESET}")
    
    print(f"{'='*70}\n")
    
    return 0 if pct == 100 else 1

if __name__ == "__main__":
    sys.exit(main())
