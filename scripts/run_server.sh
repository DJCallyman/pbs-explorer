#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="$REPO_ROOT/.run"
PID_FILE="$RUN_DIR/pbs-explorer.pid"
LOG_FILE="$RUN_DIR/pbs-explorer.log"
PYTHON_BIN="$REPO_ROOT/venv/bin/python"

cd "$REPO_ROOT"

if [ ! -d "venv" ]; then
  echo "Missing virtualenv at $REPO_ROOT/venv"
  echo "Create it first with: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Missing Python executable at $PYTHON_BIN"
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "No .env file found. Continuing with environment variables only."
else
  set -a
  source "$REPO_ROOT/.env"
  set +a
fi

source "$REPO_ROOT/venv/bin/activate"

mkdir -p "$RUN_DIR"

HOST="${PBS_EXPLORER_SERVER_HOST:-127.0.0.1}"
PORT="${PBS_EXPLORER_SERVER_PORT:-8000}"
WEB_USERNAME="${PBS_EXPLORER_WEB_USERNAME:-}"
WEB_PASSWORD="${PBS_EXPLORER_WEB_PASSWORD:-}"
TRUSTED_HOSTS="${PBS_EXPLORER_SERVER_TRUSTED_HOSTS:-127.0.0.1,localhost,::1,testserver}"
HAS_MANAGED_USERS="$("$PYTHON_BIN" - <<'PY'
from services.auth_store import has_users
print("1" if has_users() else "0")
PY
)"

find_listener_pid() {
  lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

export PBS_EXPLORER_DB_TYPE="${PBS_EXPLORER_DB_TYPE:-sqlite}"
export PBS_EXPLORER_DB_PATH="${PBS_EXPLORER_DB_PATH:-./pbs_data.db}"

requires_web_auth() {
  local host_item
  if [ "$HOST" != "127.0.0.1" ] && [ "$HOST" != "localhost" ] && [ "$HOST" != "::1" ]; then
    return 0
  fi

  OLDIFS="$IFS"
  IFS=","
  for host_item in $TRUSTED_HOSTS; do
    host_item="$(echo "$host_item" | xargs)"
    if [ -n "$host_item" ] && [ "$host_item" != "127.0.0.1" ] && [ "$host_item" != "localhost" ] && [ "$host_item" != "::1" ] && [ "$host_item" != "testserver" ]; then
      IFS="$OLDIFS"
      return 0
    fi
  done
  IFS="$OLDIFS"
  return 1
}

if [ -z "${PBS_EXPLORER_PBS_SUBSCRIPTION_KEY:-}" ] || [ "${PBS_EXPLORER_PBS_SUBSCRIPTION_KEY:-}" = "your_subscription_key_here" ]; then
  echo "Missing PBS API subscription key."
  echo "Set PBS_EXPLORER_PBS_SUBSCRIPTION_KEY in your environment or create $REPO_ROOT/.env from .env.example."
  exit 1
fi

if requires_web_auth; then
  if { [ -z "$WEB_USERNAME" ] || [ -z "$WEB_PASSWORD" ]; } && [ "$HAS_MANAGED_USERS" != "1" ]; then
    echo "Refusing to start without web authentication for this remote-access configuration."
    echo "Set PBS_EXPLORER_WEB_USERNAME and PBS_EXPLORER_WEB_PASSWORD in .env first, or create managed users in data/auth/users.json."
    exit 1
  fi
fi

if [ -f "$PID_FILE" ]; then
  EXISTING_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" 2>/dev/null; then
    echo "PBS Explorer is already running on PID $EXISTING_PID"
    echo "Stop it first with: $REPO_ROOT/scripts/stop_server.sh"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

LISTENER_PID="$(find_listener_pid)"
if [ -n "$LISTENER_PID" ]; then
  echo "Port $PORT is already in use by PID $LISTENER_PID."
  echo "Stop it first with: $REPO_ROOT/scripts/stop_server.sh"
  exit 1
fi

echo "Starting PBS Explorer on http://$HOST:$PORT"
echo "Logs: $LOG_FILE"
nohup "$PYTHON_BIN" -m uvicorn main:app --host "$HOST" --port "$PORT" --access-log --log-level info < /dev/null > "$LOG_FILE" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"
disown "$SERVER_PID" 2>/dev/null || true
sleep 2

if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "Server failed to start. Recent log output:"
  tail -n 40 "$LOG_FILE" 2>/dev/null || true
  rm -f "$PID_FILE"
  exit 1
fi

echo "Started with PID $SERVER_PID"
