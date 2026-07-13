#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
VENV_DIR="${PROJECT_ROOT}/.venv"

echo "==> Setting up email_platform development environment"

if ! command -v python3.13 &>/dev/null; then
    echo "Python 3.13 is required. Install it before continuing."
    exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
    python3.13 -m venv "${VENV_DIR}"
fi

# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

pip install --upgrade pip
pip install -r "${BACKEND_DIR}/requirements.txt"

if [ ! -f "${PROJECT_ROOT}/.env" ]; then
    cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
    echo "Created .env from .env.example — update credentials before running."
fi

cd "${BACKEND_DIR}"
export DJANGO_SETTINGS_MODULE=config.settings.development
python manage.py migrate
python manage.py collectstatic --noinput

echo "==> Development setup complete"
echo "Activate: source ${VENV_DIR}/bin/activate"
echo "Run server: cd backend && python manage.py runserver"
echo "Run Celery worker: cd backend && celery -A config worker -l INFO"
echo "Run Celery beat: cd backend && celery -A config beat -l INFO"
