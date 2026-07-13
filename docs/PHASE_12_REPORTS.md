# Phase 12 — Reports & Analytics

## API Base: `/api/v1/reports/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/overview/` | Overall delivery and engagement stats |
| GET | `/campaigns/` | Per-campaign performance reports |

### Query params for GET `/campaigns/`
- `search` — filter by campaign name or subject
- `status` — filter by campaign status

## Tracking Model: `TrackingEvent`
Event types: sent, delivered, open, click, bounce, complaint, unsubscribe.

Events are linked to campaigns (and optionally subscribers). Reports aggregate these events.

## Metrics
- Open rate = opens / delivered
- Click rate = clicks / delivered
- Bounce rate = bounces / sent

## Frontend
`/reports` page: overview stats cards and campaign performance table.

Note: Tracking events are populated when campaigns are sent (Phase 9 queue system).
