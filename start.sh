#!/usr/bin/env bash
# Arb Cannon Command Center — local start script.
# Creates .venv on first run, installs requirements, then serves the FastAPI app.
# Bind address comes from ARB_CANNON_HOST / ARB_CANNON_PORT (see .env.example).

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_DIR}"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

HOST="${ARB_CANNON_HOST:-127.0.0.1}"
PORT="${ARB_CANNON_PORT:-8000}"

echo "Starting Arb Cannon at http://${HOST}:${PORT}"
exec uvicorn app:app --host "${HOST}" --port "${PORT}" --reload
