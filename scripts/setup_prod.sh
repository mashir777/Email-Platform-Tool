#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
VENV_DIR="${PROJECT_ROOT}/.venv"
DEPLOY_DIR="${DEPLOY_DIR:-/var/www/email_platform}"

echo "==> Production setup for email_platform at ${DEPLOY_DIR}"

sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev \
    build-essential pkg-config \
    default-libmysqlclient-dev \
    nginx supervisor redis-server

if [ ! -d "${VENV_DIR}" ]; then
    python3.13 -m venv "${VENV_DIR}"
fi

# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

pip install --upgrade pip
pip install -r "${BACKEND_DIR}/requirements.txt"

if [ ! -f "${PROJECT_ROOT}/.env" ]; then
    echo "ERROR: .env file is required for production. Copy .env.example and configure."
    exit 1
fi

cd "${BACKEND_DIR}"
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py migrate --noinput
python manage.py collectstatic --noinput

sudo cp "${PROJECT_ROOT}/deployment/nginx/email_platform.conf" \
    /etc/nginx/sites-available/email_platform
sudo ln -sf /etc/nginx/sites-available/email_platform \
    /etc/nginx/sites-enabled/email_platform

sudo cp "${PROJECT_ROOT}/deployment/supervisor/email_platform.conf" \
    /etc/supervisor/conf.d/email_platform.conf

sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart email_platform:*

sudo nginx -t
sudo systemctl reload nginx

echo "==> Production setup complete"
