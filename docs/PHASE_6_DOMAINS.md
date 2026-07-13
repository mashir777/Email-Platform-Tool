# Phase 6 — Sending Domains

## API Base: `/api/v1/domains/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats/` | Domain statistics |
| GET/POST | `/` | List / add sending domains |
| GET/PATCH/DELETE | `/{id}/` | Domain detail operations |
| POST | `/{id}/default/` | Set default sending domain |
| POST | `/{id}/verify/` | Verify DNS records |

### Query params for GET `/`
- `search` — filter by domain name
- `status` — pending, verified, failed

### DNS Records (auto-generated per domain)
1. **Ownership TXT** — `_emailplatform-verify.{domain}`
2. **SPF TXT** — root domain
3. **DKIM TXT** — `{selector}._domainkey.{domain}`
4. **DMARC TXT** — `_dmarc.{domain}`

Ownership verification is required. SPF/DKIM/DMARC are tracked separately.

## Model: `SendingDomain`
Fields: domain, status, verification token, DKIM keys (encrypted private key), DNS verification flags, default/active flags.

## Frontend
`/domains` page: stats, domain list, DNS record instructions, verify, set default, delete.
