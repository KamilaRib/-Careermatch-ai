#!/usr/bin/env bash
# Inicializa backend (8000) e frontend (5173) para desenvolvimento local.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/.env" ] || { cp "$ROOT/.env.example" "$ROOT/.env"; echo "Configure sua chave de IA em .env"; }
cd "$ROOT/backend"
[ -d .venv ] || { python3 -m venv .venv; .venv/bin/pip install -r requirements-dev.txt; }
.venv/bin/uvicorn app.main:app --reload --port 8000 &
cd "$ROOT/frontend"
[ -d node_modules ] || npm install
npm run dev
