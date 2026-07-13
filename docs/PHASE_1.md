# Phase 1 — Project Foundation

Phase 1 establishes the project skeleton, configuration, and deployment tooling.

## Completed in Phase 1

- Monorepo structure (`backend`, `frontend`, `deployment`, `docs`, `scripts`)
- Django 5.x project with split settings (`base`, `development`, `production`)
- Environment variable management via `django-environ`
- MySQL, Redis, Celery, and Celery Beat configuration
- Django REST Framework and JWT authentication setup (configuration only)
- CORS, logging, static/media file handling
- Custom `User` model in `accounts` app
- Gunicorn, Nginx, and Supervisor deployment configs
- Frontend Vite + React + TypeScript + Tailwind scaffold

## Not in Phase 1 (Future Phases)

- REST API endpoints
- Business logic (campaigns, subscribers, sending, etc.)
- Authentication views and serializers
- Additional domain models

## Architecture

```
email_platform/
├── backend/          # Django application
├── frontend/         # React SPA
├── deployment/     # Gunicorn, Nginx, Supervisor
├── docs/             # Documentation
└── scripts/          # Setup and utility scripts
```

## Django Apps

| App | Purpose |
|-----|---------|
| `core` | Shared utilities and exception handling |
| `accounts` | User management (custom User model) |
| `campaigns` | Campaign management (Phase 2+) |
| `subscribers` | Subscriber lists (Phase 2+) |
| `smtp_servers` | SMTP configuration (Phase 2+) |
| `domains` | Sending domains (Phase 2+) |
| `tracking` | Open/click tracking (Phase 2+) |
| `analytics` | Analytics (Phase 2+) |
| `sending` | Email dispatch (Phase 2+) |
| `reports` | Reporting (Phase 2+) |
| `email_templates` | Templates (Phase 2+) |
| `settings_app` | Platform settings (Phase 2+) |
| `billing` | Billing (Phase 2+) |
| `api` | API routing (Phase 2+) |
