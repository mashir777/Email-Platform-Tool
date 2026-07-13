# Phase 9 — Queue System / Email Sending

## Overview
Campaigns can be sent immediately or scheduled. Delivery uses the owner's default SMTP server when configured; otherwise Django's email backend (console in local development).

## API
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/campaigns/{id}/send/` | Queue and send campaign now |

## Flow
1. Validate campaign (list, subject, content, active subscribers)
2. Create `EmailQueueItem` rows per subscribed recipient
3. Set campaign status → `sending`
4. Celery task sends each item via SMTP (or Django mail)
5. Create `TrackingEvent` (`sent`) per successful delivery
6. When queue complete → campaign status `sent`

## Models
- `sending.EmailQueueItem` — pending/sending/sent/failed/skipped per recipient

## Tasks
- `sending.tasks.dispatch_campaign` — queue + fan-out
- `sending.tasks.process_email_queue_item` — send one email
- `sending.tasks.process_due_scheduled_campaigns` — Beat every 60s

## Personalization
Supported placeholders: `{{email}}`, `{{first_name}}`, `{{last_name}}`, `{{full_name}}`

## Local development
- `CELERY_TASK_ALWAYS_EAGER=True` — send runs inline (no Redis worker needed)
- Default email backend prints to console unless SMTP Providers are configured
- Add an active/default SMTP server under **SMTP** to deliver through real SMTP
