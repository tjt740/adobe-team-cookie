#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR/payload/backend"

if [ ! -x .venv/bin/python ]; then
  echo "Missing backend virtual environment: create .venv and install requirements.txt first." >&2
  exit 1
fi

exec .venv/bin/python -m uvicorn run_local:app --host 127.0.0.1 --port "${ADOBETEAM_PORT:-18080}"
