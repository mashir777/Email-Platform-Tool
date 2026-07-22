#!/usr/bin/env bash
# Start (or rebuild) the full stack on EC2.
# Usage:
#   ./scripts/docker-up.sh
#   ./scripts/docker-up.sh --profile reacher
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy the Docker example first:"
  echo "  cp .env.docker.example .env"
  echo "Then edit .env (DJANGO_SECRET_KEY, POSTGRES_PASSWORD, domain, SMTP...)."
  exit 1
fi

echo "Building and starting containers..."
docker compose --env-file .env up -d --build "$@"

echo
echo "Status:"
docker compose ps

echo
echo "App should be on http://SERVER_IP (or your domain)."
echo "Logs:  docker compose logs -f"
echo "Stop:  ./scripts/docker-down.sh"
