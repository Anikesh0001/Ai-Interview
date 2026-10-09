#!/usr/bin/env bash
# Runs the backend (port 8000) and the Vite dev server (port 5173) together. Ctrl+C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/backend/.venv/bin/python"
# Check the backend can actually start before launching anything, instead of leaving Vite
# running against a dead API.
if ! "$PY" -c "import fastapi, uvicorn, pymupdf" 2>/dev/null; then
  echo "The backend environment is missing or broken (e.g. the project folder was moved)."
  echo "Run 'make install' first."
  exit 1
fi
[ -d frontend/node_modules ] || { echo "Frontend dependencies missing. Run 'make install' first."; exit 1; }
trap 'kill 0' EXIT INT TERM
(cd backend && "$PY" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
(cd frontend && npx vite --port 5173) &
echo ""
echo "  InterviewForge → http://localhost:5173   (API: http://localhost:8000/docs)"
echo ""
wait
