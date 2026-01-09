@echo off
REM Serve LegalRAG documentation locally (Windows)

echo.
echo 🚀 LegalRAG Documentation Server
echo ================================
echo.

REM Check if in correct directory
if not exist "mkdocs.yml" (
    echo ❌ Error: mkdocs.yml not found
    echo    Please run this script from the project root directory
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv_docs" (
    echo 📦 Creating virtual environment...
    python -m venv venv_docs
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv_docs\Scripts\activate.bat

REM Install dependencies
echo 📥 Installing MkDocs dependencies...
pip install -q -r docs_site\requirements.txt

REM Serve documentation
echo.
echo ✅ Starting documentation server...
echo 📖 Open http://127.0.0.1:8000 in your browser
echo.
echo Press Ctrl+C to stop the server
echo.

mkdocs serve
