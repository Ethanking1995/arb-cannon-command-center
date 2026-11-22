#!/usr/bin/env bash
# Arb Cannon: M&A Rumor & Leak Arbitrage Dashboard — local start script.
# Bootstraps .venv if needed, stops any stale Arb Cannon server, serves the
# M&A Overnight Scanner & Biotech Rumors UI on port 8088 (avoiding port 8000
# conflicts), and opens the dashboard in your default browser.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_DIR}"

FORCE_INSTALL=0
NO_OPEN="${ARB_CANNON_NO_OPEN:-0}"
CLI_PORT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --install|--upgrade)
      FORCE_INSTALL=1
      shift
      ;;
    --no-open)
      NO_OPEN=1
      shift
      ;;
    --port)
      CLI_PORT="${2:?--port requires a port number}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

ENV_HOST="${ARB_CANNON_HOST:-}"
ENV_PORT="${ARB_CANNON_PORT:-}"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

HOST="${ENV_HOST:-${ARB_CANNON_HOST:-127.0.0.1}}"
PORT="${CLI_PORT:-${ENV_PORT:-${ARB_CANNON_PORT:-8088}}}"

# 1. Bootstrap Python virtual environment & dependencies if needed
if [ ! -x ".venv/bin/python" ]; then
  echo "[Arb Cannon] Creating Python virtual environment (.venv)..."
  PYTHON_BOOT="python3"
  if [ -x "/usr/bin/python3" ] && python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 15) else 1)" 2>/dev/null; then
    PYTHON_BOOT="/usr/bin/python3"
  fi
  "${PYTHON_BOOT}" -m venv .venv
fi

VENV_PY="${PROJECT_DIR}/.venv/bin/python"
VENV_UVICORN="${PROJECT_DIR}/.venv/bin/uvicorn"

if [ "${FORCE_INSTALL}" = "1" ] || ! "${VENV_PY}" -c "import fastapi, uvicorn, httpx, requests, yfinance, dotenv, pydantic" >/dev/null 2>&1; then
  echo "[Arb Cannon] Installing Python dependencies..."
  "${VENV_PY}" -m pip install -q --upgrade pip
  "${VENV_PY}" -m pip install -q -r requirements.txt
fi

# 2. Stop any previously running Arb Cannon uvicorn instance from this project
ARB_TARGET="${VENV_UVICORN} app:app" "${VENV_PY}" - <<'PY'
import os
import signal
import subprocess
import time

target = os.environ["ARB_TARGET"]
skip = {os.getpid(), os.getppid()}
out = subprocess.check_output(["ps", "-axo", "pid=,command="], text=True)
pids = []
for line in out.splitlines():
    parts = line.strip().split(None, 1)
    if len(parts) == 2 and parts[0].isdigit():
        pid = int(parts[0])
        if pid not in skip and target in parts[1]:
            pids.append(pid)

if pids:
    print(f"[Arb Cannon] Stopping previous Arb Cannon server (PID: {' '.join(map(str, pids))})...")
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(1.0)
PY

# 3. Fall back to the next open port if the requested port is busy with another app
PORT="$("${VENV_PY}" - "${HOST}" "${PORT}" <<'PY'
import socket
import sys

host = sys.argv[1]
requested = int(sys.argv[2])

def is_free(port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if probe.connect_ex((host, port)) == 0:
            return False
    finally:
        probe.close()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()

if is_free(requested):
    print(requested)
else:
    for candidate in range(requested + 1, requested + 100):
        if is_free(candidate):
            print(candidate)
            break
    else:
        raise SystemExit(f"No open port found near {requested}")
PY
)"

URL="http://${HOST}:${PORT}/"

echo "[Arb Cannon] Starting M&A Rumor & Overnight Scanner Dashboard at ${URL}"
echo "  - M&A Overnight Scanner: ${URL}"
echo "  - Biotech M&A Rumors:    http://${HOST}:${PORT}/biotech-rumors"
echo "  - Classic Dark Terminal: http://${HOST}:${PORT}/terminal"

# 4. Automatically open the M&A rumors dashboard once the server starts listening
if [ "${NO_OPEN}" != "1" ] && command -v open >/dev/null 2>&1; then
  (
    for _ in $(seq 1 40); do
      if "${VENV_PY}" -c "import socket, sys; s = socket.socket(); r = s.connect_ex(('${HOST}', ${PORT})); s.close(); sys.exit(0 if r == 0 else 1)" 2>/dev/null; then
        open "${URL}" >/dev/null 2>&1 || true
        exit 0
      fi
      sleep 0.25
    done
  ) &
fi

exec "${VENV_UVICORN}" app:app --host "${HOST}" --port "${PORT}" --reload
