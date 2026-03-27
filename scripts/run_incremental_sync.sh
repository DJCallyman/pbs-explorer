#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$REPO_ROOT"

if [ ! -d "venv" ]; then
  echo "Missing virtualenv at $REPO_ROOT/venv"
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "Missing .env file at $REPO_ROOT/.env"
  exit 1
fi

source "$REPO_ROOT/venv/bin/activate"

exec python -m tasks.sync_incremental
