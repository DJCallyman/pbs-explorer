#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="$REPO_ROOT/.run"
PID_FILE="$RUN_DIR/pbs-explorer.pid"
HOST="${PBS_EXPLORER_SERVER_HOST:-127.0.0.1}"
PORT="${PBS_EXPLORER_SERVER_PORT:-8000}"

find_listener_pid() {
  lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

stop_pid() {
  local pid="$1"
  if [ -z "$pid" ]; then
    return 1
  fi

  if ! kill -0 "$pid" 2>/dev/null; then
    return 1
  fi

  echo "Stopping PBS Explorer (PID $pid)..."
  kill "$pid"

  for _ in {1..20}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep 0.5
  done

  echo "Process did not exit promptly. Sending SIGKILL."
  kill -9 "$pid" 2>/dev/null || true
  return 0
}

if [ ! -f "$PID_FILE" ]; then
  LISTENER_PID="$(find_listener_pid)"
  if [ -n "$LISTENER_PID" ]; then
    echo "No PID file found, but port $PORT is in use by PID $LISTENER_PID."
    stop_pid "$LISTENER_PID"
    echo "Stopped."
    exit 0
  fi
  echo "No PID file found. PBS Explorer does not look like it is running."
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -z "$PID" ]; then
  echo "PID file was empty. Cleaning it up."
  rm -f "$PID_FILE"
  LISTENER_PID="$(find_listener_pid)"
  if [ -n "$LISTENER_PID" ]; then
    echo "Found listener on port $PORT with PID $LISTENER_PID."
    stop_pid "$LISTENER_PID"
    echo "Stopped."
  fi
  exit 0
fi

if ! kill -0 "$PID" 2>/dev/null; then
  echo "No running process found for PID $PID. Cleaning up stale PID file."
  rm -f "$PID_FILE"
  LISTENER_PID="$(find_listener_pid)"
  if [ -n "$LISTENER_PID" ]; then
    echo "Found listener on port $PORT with PID $LISTENER_PID."
    stop_pid "$LISTENER_PID"
    echo "Stopped."
  fi
  exit 0
fi

stop_pid "$PID"
rm -f "$PID_FILE"
echo "Stopped."
