#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
api=$!
trap 'kill "$api" 2>/dev/null || true' EXIT INT TERM
cd frontend
npm run dev
