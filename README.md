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

## Deploy Frontend to Vercel

The React frontend is configured for Vercel (`vercel.json` at repo root).

1. Push this repo to GitHub (already set as `origin`).
2. Go to [vercel.com](https://vercel.com) → **Add New Project** → import `mashir777/Email-Platform-Tool`.
3. Set **Root Directory** to `frontend` (required).
4. Build settings should be: Install `npm install`, Build `npm run build`, Output `dist`.
5. Add Environment Variable:
   - `VITE_API_BASE_URL` = your public Django API URL (e.g. `https://api.yourdomain.com`) — **not** `localhost`
6. Deploy. Your app URL will look like `https://email-platform-tool.vercel.app`.

**Important:** Only the frontend runs on Vercel. Django (MySQL, Redis, Celery) must stay on a VPS / Railway / Render / Cloudflare Tunnel. After you have the Vercel URL, set on the backend:

```env
FRONTEND_URL=https://your-app.vercel.app
CORS_ALLOWED_ORIGINS=...,https://your-app.vercel.app
CSRF_TRUSTED_ORIGINS=...,https://your-app.vercel.app
```

Then restart Django.

## Production Deployment (Backend / VPS)

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
