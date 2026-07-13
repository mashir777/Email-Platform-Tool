# Phase 5 — SMTP Providers

## API Base: `/api/v1/smtp/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats/` | SMTP server statistics |
| GET/POST | `/` | List / create SMTP servers |
| GET/PATCH/DELETE | `/{id}/` | Server detail operations |
| POST | `/{id}/default/` | Set server as default |
| POST | `/{id}/test/` | Test SMTP connection |

### Query params for GET `/`
- `search` — filter by name or host

### Security
- Passwords are encrypted at rest using Fernet (`core/encryption.py`)
- Password is write-only; never returned in API responses

## Model: `SmtpServer`
Fields: name, host, port, username, encryption (none/tls/ssl), from_email, from_name, is_active, is_default, hourly_limit, daily_limit, last test metadata.

## Frontend
`/smtp` page: stats cards, server table, add/edit form, test connection, set default, delete.
