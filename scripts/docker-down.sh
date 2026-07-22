#!/usr/bin/env bash
# Stop containers. Data volumes (Postgres, media, etc.) are kept.
# Usage:
#   ./scripts/docker-down.sh
#   ./scripts/docker-down.sh --volumes   # also delete volumes (wipes DB)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Stopping containers..."
docker compose --env-file .env down "$@"

echo "Done."
