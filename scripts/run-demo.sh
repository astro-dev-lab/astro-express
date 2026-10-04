#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
if [[ ! -x .venv/bin/python || ! -f frontend/dist/index.html ]]; then
  echo 'Install the root .venv and build frontend first; see README.md.' >&2
  exit 1
fi
export APP_MODE=simulation
export DEMO_ORIGIN=http://127.0.0.1:8000
exec .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
