# Phase 7 — Campaign Builder

## API: `/api/v1/campaigns/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats/` | Campaign statistics |
| GET/POST | `/` | List / create campaigns |
| GET/PATCH/DELETE | `/{id}/` | Campaign detail |
| POST | `/{id}/schedule/` | Schedule draft campaign |
| POST | `/{id}/cancel/` | Cancel scheduled campaign |
| POST | `/{id}/duplicate/` | Duplicate campaign |

## Campaign Statuses
`draft` → `scheduled` → `sending` → `sent` (sending/sent wired in Phase 9)

## Note
Scheduling stores the campaign; actual email dispatch requires Phase 9 (Queue System).
