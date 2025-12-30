#!/usr/bin/env bash
set -euo pipefail

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# Ensure we kill both child processes on exit
cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID"
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID"
  fi
}
trap cleanup EXIT INT TERM

echo "Starting AXI API on ${BACKEND_HOST}:${BACKEND_PORT}..."
python -m uvicorn axi.api.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
BACKEND_PID=$!

echo "Starting frontend (Vite) on ${FRONTEND_PORT}..."
(cd frontend && npm run dev -- --host --port "$FRONTEND_PORT") &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID | Frontend PID: $FRONTEND_PID"
echo "UI: http://${BACKEND_HOST}:${FRONTEND_PORT} (Vite) -> API: http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "Press Ctrl+C to stop both."

wait -n
