#!/bin/bash
# Script to fix Vite cache and module resolution issues

echo "Clearing Vite cache..."
rm -rf node_modules/.vite
rm -rf dist
rm -rf .vite

echo "Clearing npm cache for vis-network..."
npm cache clean --force 2>/dev/null || true

echo "Reinstalling dependencies..."
npm install

echo ""
echo "Done! Now restart your dev server with: npm run dev"
echo ""
echo "If the issue persists, try:"
echo "1. Stop the dev server (Ctrl+C)"
echo "2. Run: rm -rf node_modules/.vite dist .vite"
echo "3. Run: npm run dev"















