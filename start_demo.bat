@echo off
chcp 65001 > nul
echo ⚖️ LegalRAG — Demo Startup
echo ===========================
echo.

:: Check Docker
echo [1/5] Checking Docker containers...
docker ps --format "  {{.Names}}: {{.Status}}" 2>nul
if %errorlevel% neq 0 (
    echo ❌ Docker is not running! Start Docker Desktop first.
    pause
    exit /b 1
)
echo.

:: Check .env
if not exist .env (
    echo ❌ .env file not found! Copy .env.example to .env and add your GEMINI_API_KEY.
    pause
    exit /b 1
)

:: Check API key (warn if placeholder)
findstr /C:"your_gemini_api_key_here" .env > nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  WARNING: GEMINI_API_KEY is still a placeholder!
    echo    Edit .env and set your real Gemini API key for full RAG functionality.
    echo.
)

:: Start infrastructure if not running
docker ps | findstr "legal_rag_postgres" > nul 2>&1
if %errorlevel% neq 0 (
    echo [2/5] Starting infrastructure...
    docker-compose up -d
    docker-compose -f docker-compose.neo4j.yml up -d
    timeout /t 10 /nobreak > nul
) else (
    echo [2/5] Infrastructure already running ✅
)
echo.

:: Set PYTHONPATH
set PYTHONPATH=%cd%

:: Start API Gateway
echo [3/5] Starting API Gateway on :8080...
start "LegalRAG - API Gateway" cmd /c "set PYTHONPATH=%cd% && python scripts/start_microservices.py --port 8080"
timeout /t 5 /nobreak > nul
echo.

:: Start Chainlit
echo [4/5] Starting Chat UI on :8501...
start "LegalRAG - Chainlit" cmd /c "set PYTHONPATH=%cd% && chainlit run chainlit_app.py --port 8501 --host 0.0.0.0"
timeout /t 3 /nobreak > nul
echo.

:: Start Admin Panel
echo [5/5] Starting Admin Panel on :8090...
start "LegalRAG - Admin Panel" cmd /c "set PYTHONPATH=%cd% && streamlit run admin_panel/app.py --server.port 8090 --server.headless true"
timeout /t 3 /nobreak > nul
echo.

echo ===========================
echo ✅ LegalRAG is starting up!
echo.
echo   💬 Chat UI:     http://localhost:8501
echo   📊 Admin Panel: http://localhost:8090
echo   🔌 API Gateway: http://localhost:8080
echo   📋 API Health:  http://localhost:8080/health
echo.
echo Press any key to close this window (services keep running)...
pause > nul
