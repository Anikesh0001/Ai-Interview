#!/usr/bin/env bash
# Starts the backend for Playwright E2E runs: TEST_MODE (no Ollama), fresh throwaway database.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
E2E_DIR="${E2E_DATA_DIR:-$ROOT/data/e2e}"
rm -rf "$E2E_DIR"
mkdir -p "$E2E_DIR/uploads"
cd "$ROOT/backend"
export TEST_MODE=true
export DATABASE_URL="sqlite:///$E2E_DIR/e2e.db"
export UPLOAD_DIR="$E2E_DIR/uploads"
export FRONTEND_DIST=/nonexistent
export CORS_ORIGINS="http://localhost:5174,http://127.0.0.1:5174"
PY="${PYTHON:-$ROOT/backend/.venv/bin/python}"
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "${E2E_API_PORT:-8001}"
