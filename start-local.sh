#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR/payload/backend"

if [ ! -x .venv/bin/python ]; then
  echo "Missing backend virtual environment: create .venv and install requirements.txt first." >&2
  exit 1
fi

exec .venv/bin/python "$PROJECT_DIR/deploy/mihomo/local.py"
