#!/usr/bin/env bash
# Follow logs for all (or one) service.
# Usage:
#   ./scripts/docker-logs.sh
#   ./scripts/docker-logs.sh backend
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose --env-file .env logs -f "$@"
