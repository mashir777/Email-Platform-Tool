# Phase 4 — Subscriber Module

## API Base: `/api/v1/subscribers/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats/` | Subscriber statistics |
| GET/POST | `/lists/` | List subscriber lists / create list |
| GET/PATCH/DELETE | `/lists/{id}/` | List detail operations |
| GET/POST | `/` | List/create subscribers |
| GET/PATCH/DELETE | `/{id}/` | Subscriber detail |
| POST | `/import/` | CSV import (multipart) |
| POST | `/bulk-delete/` | Bulk delete by IDs |

### Query params for GET `/`
- `list_id` — filter by list
- `status` — subscribed, unsubscribed, bounced, complained
- `search` — email/name search

### CSV Import
Required column: `email`. Optional: `first_name`, `last_name`, `phone`.

## Models
- `SubscriberList` — contact lists per user
- `Subscriber` — email contacts per user
- `ListMembership` — M2M through table

## Frontend
`/subscribers` page: stats, list sidebar, contacts table, add/import/delete.
