# Email Platform Tool

Production-grade SaaS Email Marketing Platform — enterprise-level, scalable, and modular.

**Repo:** [mashir777/Email-Platform-Tool](https://github.com/mashir777/Email-Platform-Tool)

**Phase 1** delivers the project foundation: Django backend scaffolding, configuration, custom User model, deployment tooling, and a React frontend scaffold.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.13, Django 5.x, DRF, JWT |
| Database | MySQL 8 |
| Cache / Queue | Redis, Celery, Celery Beat |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Deployment | Ubuntu 24.04, Gunicorn, Nginx, Supervisor |

## Project Structure

```
email_platform/
├── backend/                 # Django project
│   ├── config/              # Settings, URLs, Celery, WSGI
│   ├── accounts/            # Custom User model
│   ├── core/                # Shared utilities
│   ├── campaigns/           # (Phase 2+)
│   ├── subscribers/         # (Phase 2+)
│   ├── smtp_servers/        # (Phase 2+)
│   ├── domains/             # (Phase 2+)
│   ├── tracking/            # (Phase 2+)
│   ├── analytics/           # (Phase 2+)
│   ├── sending/             # (Phase 2+)
│   ├── reports/             # (Phase 2+)
│   ├── email_templates/     # (Phase 2+)
│   ├── settings_app/        # (Phase 2+)
│   ├── billing/             # (Phase 2+)
│   ├── api/                 # (Phase 2+)
│   ├── manage.py
│   └── requirements.txt
├── frontend/                # React SPA scaffold
├── deployment/              # Gunicorn, Nginx, Supervisor
├── docs/                    # Documentation
├── scripts/                 # Setup scripts
├── .env.example
└── README.md
```

## Quick Start (Development)

### Prerequisites

- Python 3.13
- Node.js 20+
- MySQL 8
- Redis

### Backend

```bash
# Clone and configure
cp .env.example .env
# Edit .env with your MySQL and Redis credentials

# Setup (Linux/macOS)
chmod +x scripts/setup_dev.sh
./scripts/setup_dev.sh

# Or manually:
python3.13 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend
export DJANGO_SETTINGS_MODULE=config.settings.development
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Celery (separate terminals)

```bash
cd backend
celery -A config worker -l INFO
celery -A config beat -l INFO
```

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

## Docker deploy (AWS EC2)

Runs Postgres, Redis, Django (Gunicorn), Celery worker + beat, and the React SPA behind nginx on port 80.

```bash
# On the EC2 instance (Ubuntu), install Docker first if needed:
#   curl -fsSL https://get.docker.com | sudo sh
#   sudo usermod -aG docker $USER   # then re-login

cd /path/to/Email-Platform-Tool
cp .env.docker.example .env
nano .env   # set DJANGO_SECRET_KEY, POSTGRES_PASSWORD, domain/IP, SMTP

chmod +x scripts/docker-*.sh
./scripts/docker-up.sh              # build + start
# ./scripts/docker-up.sh --profile reacher   # also start Reacher verifier

./scripts/docker-logs.sh            # follow logs
./scripts/docker-down.sh            # stop (keeps DB/media volumes)

docker compose exec backend python manage.py createsuperuser
```

Open security group port **80** (and **443** later for HTTPS). After code changes on the server: `./scripts/docker-up.sh` again to rebuild and restart.

## Deploy Frontend + Django API to Vercel

Signup/login HTTP API can run on Vercel. Campaign queues (Celery workers) still need a real VPS later.

### 1) Create a free Postgres database

Use [Neon](https://neon.tech) or Vercel Storage → Postgres. Copy the `DATABASE_URL`.

### 2) Vercel project settings

1. Framework Preset: **Services** (required for monorepo `vercel.json` services)
2. Root Directory: **`.`** (repo root — not `frontend`)
3. Env vars (Production + Preview):

| Name | Example |
|------|---------|
| `DJANGO_SECRET_KEY` | long random string |
| `DJANGO_SETTINGS_MODULE` | `config.settings.vercel` |
| `DATABASE_URL` | `postgresql://...` from Neon |
| `DJANGO_ALLOWED_HOSTS` | `.vercel.app` |
| `EMAIL_HOST` | `smtp.gmail.com` |
| `EMAIL_PORT` | `587` |
| `EMAIL_USE_TLS` | `True` |
| `EMAIL_HOST_USER` | your Gmail |
| `EMAIL_HOST_PASSWORD` | Gmail app password |
| `DEFAULT_FROM_EMAIL` | your Gmail |

**Do not set** `VITE_API_BASE_URL` (leave empty). The app calls same-origin `/api/...`.

### 3) Redeploy

Push to `main` or click Redeploy. Build runs `migrate` automatically.

### 4) Test

Open your Vercel URL → Signup. Verification email sends in-request (Celery eager mode).

Campaign sending / Celery Beat still need a VPS later — this Vercel setup is for **auth API + UI** only.

## Production Deployment (Full Backend / VPS)

See deployment guides:

- [Nginx Guide](deployment/nginx/NGINX_GUIDE.md)
- [Supervisor Guide](deployment/supervisor/SUPERVISOR_GUIDE.md)
- Gunicorn config: `deployment/gunicorn/gunicorn.conf.py`

```bash
chmod +x scripts/setup_prod.sh
./scripts/setup_prod.sh
```

## Configuration

Environment variables are defined in `.env.example`. Key settings:

| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Django secret key |
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` or `config.settings.production` |
| `DB_*` | MySQL connection |
| `REDIS_URL` | Redis cache |
| `CELERY_BROKER_URL` | Celery message broker |
| `JWT_*` | Token lifetimes |
| `CORS_ALLOWED_ORIGINS` | Frontend origins |

## Django Apps (Phase 1)

All apps are registered and ready. Only `accounts.User` is implemented as a model.

## Phase 1 Scope

- Project structure and configuration
- Custom User model (`accounts.User`)
- JWT / DRF / CORS / Celery configuration (no endpoints)
- Deployment configs (Gunicorn, Nginx, Supervisor)
- Frontend scaffold

## Phase 2 — Authentication (Complete)

See [docs/PHASE_2_AUTHENTICATION.md](docs/PHASE_2_AUTHENTICATION.md).

## Phase 3 — Dashboard UI (Complete)

React admin panel with login, sidebar, dashboard, and module shells.

See [docs/PHASE_3_DASHBOARD.md](docs/PHASE_3_DASHBOARD.md).

## Phase 4 — Subscribers (Complete)

Full subscriber module with Django API and React UI.

See [docs/PHASE_4_SUBSCRIBERS.md](docs/PHASE_4_SUBSCRIBERS.md).

```bash
cd frontend && npm install && npm run dev
```

## License

Proprietary — All rights reserved.
