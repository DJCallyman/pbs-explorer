#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
BUNDLE_NAME="pbs-explorer-deploy-${TIMESTAMP}.tar.gz"
BUNDLE_PATH="$DIST_DIR/$BUNDLE_NAME"
INCLUDE_DB="true"

if [ "${1:-}" = "--without-db" ]; then
  INCLUDE_DB="false"
fi

mkdir -p "$DIST_DIR"

cd "$REPO_ROOT"

EXCLUDES=(
  --exclude=".git"
  --exclude=".github"
  --exclude="venv"
  --exclude=".run"
  --exclude="dist"
  --exclude="logs"
  --exclude="__pycache__"
  --exclude="*/__pycache__"
  --exclude=".DS_Store"
  --exclude=".env"
  --exclude="*.pyc"
)

if [ "$INCLUDE_DB" != "true" ]; then
  EXCLUDES+=(--exclude="pbs_data.db")
fi

tar -czf "$BUNDLE_PATH" "${EXCLUDES[@]}" .

echo "Created deployment bundle:"
echo "$BUNDLE_PATH"
if [ "$INCLUDE_DB" = "true" ]; then
  echo "Included: application code + SQLite database"
else
  echo "Included: application code only"
fi
