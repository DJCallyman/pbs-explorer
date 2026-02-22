#!/bin/sh
set -e

# Fix ownership of the data directory (mounted volume may be root-owned)
chown -R appuser:appgroup /app/data 2>/dev/null || true

# Drop to non-root user and exec the CMD
exec su -s /bin/sh appuser -c "$*"
