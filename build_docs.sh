#!/bin/bash
# Build LegalRAG documentation for production deployment

set -e

echo "🏗️ LegalRAG Documentation Build"
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

# Build documentation
echo ""
echo "🔨 Building static site..."
mkdocs build

# Success message
echo ""
echo "✅ Documentation built successfully!"
echo "📁 Output directory: site/"
echo ""
echo "To deploy:"
echo "  - Upload 'site/' directory to web server"
echo "  - Or use: mkdocs gh-deploy (for GitHub Pages)"
echo ""
