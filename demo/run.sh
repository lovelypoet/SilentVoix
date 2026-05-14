#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="${PYTHON:-python3.11}"
if ! command -v "$PYTHON" &>/dev/null; then
  PYTHON="python3"
fi

echo "=== SilentVoix Competition Demo ==="
echo ""

start_backend() {
  echo "[backend] Installing deps... (using $PYTHON)"
  $PYTHON -m pip install -q -r backend/requirements.txt 2>/dev/null
  echo "[backend] Starting server on :8000..."
  cd backend
  $PYTHON -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
  BACKEND_PID=$!
  cd "$SCRIPT_DIR"
}

start_frontend() {
  echo "[frontend] Installing deps..."
  cd frontend
  npm install --silent 2>/dev/null
  echo "[frontend] Starting dev server on :5173..."
  npm run dev &
  FRONTEND_PID=$!
  cd "$SCRIPT_DIR"
}

cleanup() {
  echo ""
  echo "Shutting down..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
  exit 0
}

trap cleanup SIGINT SIGTERM

start_backend
start_frontend

echo ""
echo "  Backend  → http://localhost:8000"
echo "  Frontend → http://localhost:5173"
echo "  Demo     → http://localhost:5173/"
echo "  Test Lab → http://localhost:5173/test"
echo ""
echo "Press Ctrl+C to stop"

wait
