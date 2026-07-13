# Phase 3 — Dashboard UI (React Admin Panel)

## Completed

- React admin panel with responsive sidebar layout
- Login page wired to Phase 2 auth API (`POST /api/v1/auth/login/`)
- JWT session (localStorage + auto refresh on 401)
- Protected routes and auth guards
- Dashboard with account overview and stat placeholders
- Module shell pages: Subscribers, Campaigns, SMTP, Domains, Reports, Settings
- Mobile-friendly sidebar (drawer on small screens)

## Routes

| Path | Page | API |
|------|------|-----|
| `/login` | Login | Phase 2 auth |
| `/dashboard` | Dashboard | Profile from auth context |
| `/subscribers` | Subscribers shell | Phase 4 |
| `/campaigns` | Campaigns shell | Phase 7 |
| `/smtp` | SMTP shell | Phase 5 |
| `/domains` | Domains shell | Phase 6 |
| `/reports` | Reports shell | Phase 12 |
| `/settings` | Settings (profile read-only) | Phase 2 profile |

## Run

```bash
# Terminal 1 — Django
cd backend && python manage.py runserver

# Terminal 2 — React
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open http://localhost:5173 — login redirects to dashboard.

## Frontend Structure

```
frontend/src/
├── api/           # HTTP client + auth API calls
├── components/    # Layout, UI, auth guards
├── config/        # Navigation items
├── context/       # AuthProvider
├── lib/           # Token storage
├── pages/         # Route pages
└── types/         # TypeScript types
```

## Next Steps

Django APIs for each module (Phases 4–12) will replace placeholder pages with live data.
