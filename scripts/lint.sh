#!/bin/bash
set -e

echo "Linting Python..."
ruff check backend axi-cli

echo "Linting Frontend..."
cd frontend
npm run lint

echo "Done!"
