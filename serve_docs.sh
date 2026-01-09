#!/bin/bash
# Serve LegalRAG documentation locally

set -e

echo "🚀 LegalRAG Documentation Server"
echo "================================"

# Check if in docs_site directory
if [ ! -f "mkdocs.yml" ]; then
    echo "❌ Error: mkdocs.yml not found"
    echo "   Please run this script from the project root directory"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv_docs" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv_docs
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv_docs/bin/activate

# Install dependencies
echo "📥 Installing MkDocs dependencies..."
pip install -q -r docs_site/requirements.txt

# Serve documentation
echo ""
echo "✅ Starting documentation server..."
echo "📖 Open http://127.0.0.1:8000 in your browser"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

mkdocs serve
