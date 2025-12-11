#!/bin/bash
set -e

echo "Building Frontend..."
cd frontend
npm run build
cd ..

echo "Building Backend Wheel..."
cd backend
python -m build
cd ..

echo "Building CLI Wheel..."
cd axi-cli
python -m build
cd ..

echo "Build Complete!"
