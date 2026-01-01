#!/bin/bash
# Script to publish AXI packages to PyPI
# Usage: ./scripts/publish_to_pypi.sh [test|prod]

set -e

ENV=${1:-test}

if [ "$ENV" = "test" ]; then
    REPOSITORY="--repository testpypi"
    echo "📦 Publishing to TestPyPI..."
elif [ "$ENV" = "prod" ]; then
    REPOSITORY=""
    echo "📦 Publishing to PyPI (PRODUCTION)..."
else
    echo "Usage: $0 [test|prod]"
    exit 1
fi

# Check if package already exists
echo "🔍 Checking if package exists on PyPI..."
if curl -s "https://pypi.org/pypi/axi-semantic/json" > /dev/null 2>&1; then
    echo "⚠️  Package 'axi-semantic' already exists on PyPI!"
    echo "   Current version: $(curl -s https://pypi.org/pypi/axi-semantic/json | grep -o '"version":"[^"]*"' | head -1 | cut -d'"' -f4)"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ Package 'axi-semantic' not found on PyPI (good for first publish)"
fi

# Install build tools
echo "📥 Installing build tools..."
pip install --upgrade build twine

# Build backend package
echo "🔨 Building backend package..."
cd backend
python -m build
cd ..

# Build CLI package (if exists)
if [ -d "axi-cli" ]; then
    echo "🔨 Building CLI package..."
    cd axi-cli
    python -m build
    cd ..
fi

# Upload
echo "🚀 Uploading packages..."
if [ -d "axi-cli" ]; then
    twine upload $REPOSITORY backend/dist/* axi-cli/dist/*
else
    twine upload $REPOSITORY backend/dist/*
fi

echo "✅ Done! Check your package at:"
if [ "$ENV" = "test" ]; then
    echo "   https://test.pypi.org/project/axi-semantic/"
else
    echo "   https://pypi.org/project/axi-semantic/"
fi
