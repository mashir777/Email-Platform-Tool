# Instantly AI vs this platform (ideas only)

This is a **product map**, not a clone. Existing SMTP, Domains, Campaigns, Tracking, and Shared Reply-To stay as-is.

## Already in this app (use now)

| Capability | Where |
|------------|--------|
| Many senders (SMTP round-robin + CSV import) | **SMTP** page |
| Domains (SPF / DKIM / DMARC verify) | **Domains** page |
| Shared Reply-To (one inbox for replies) | **Settings → Shared Reply-To** (e.g. `leads@datrixworld.com`) |
| **Unibox** (IMAP replies from all senders) | **Unibox** page → Sync inboxes |
| **Warmup ramp** (per-sender daily cap increase) | **SMTP** → Enable warmup ramp |
| Lists, campaigns, open tracking | **List**, **Campaigns**, **Tracking** |

## How to use new add-ons

### Unibox
1. SMTP mailboxes must have username/password (IMAP uses SMTP host or `imap_host`).
2. Open **Unibox** → **Sync inboxes**.
3. Replies appear in one list (optional Celery beat sync every 5 min).

### Warmup
1. Edit an SMTP sender → enable **warmup ramp**.
2. Set start / target / increase per day (defaults 5 → 40, +5/day).
3. Campaign sends respect the current warmup cap until it reaches the target.
4. This is **not** Instantly’s private engagement network — only a volume ramp.

## Still later (optional)

| Instantly idea | Status |
|----------------|--------|
| Multi-step sequences | Not built |
| AI reply labels | Not built |
| Instantly 4M warmup network | Not available (their infra) |
