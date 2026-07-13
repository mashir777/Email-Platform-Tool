# Email Sending — Complete Setup Guide

This guide is for the **Email Platform** app (Django + React).  
Your MailWizz document is for a **different product** (self-hosted MailWizz on VPS).  
Below maps MailWizz steps → what you do in **this** platform.

---

## Why mail is not sending (checklist)

| Check | Where | Your status |
|-------|--------|-------------|
| Subscriber list exists | Campaigns → Edit → Subscriber list | ✅ List "new letter" exists |
| **Subscribers IN the list** | Subscribers → select list → Add contact | ❌ **0 subscribers** (main blocker) |
| SMTP server configured | SMTP → Add server → Test → Set default | ⚠️ Server exists, set as **default** |
| Campaign has subject + HTML | Campaigns → Edit | Required |
| Backend running | Terminal `python manage.py runserver` | Required |
| Frontend running | Terminal `npm run dev` | Required |

---

## Step-by-step: Send your first email (this app)

### 1. SMTP (Delivery Server)
Go to **SMTP** → **Add Server**

Example (your server):
- **Host:** `mail.datrixworld.com`
- **Port:** `587` (TLS) or `465` (SSL)
- **Username:** your mailbox user
- **Password:** mailbox password
- **From email:** same domain email (e.g. `noreply@datrixworld.com`)
- Click **Test** → must pass
- Click **Set default**

> Without SMTP, emails only print in the **backend terminal** (console mode), not real inbox.

### 2. Subscribers (Recipients)
Go to **Subscribers**:
1. Select list **"new letter"** (or create one)
2. Click **Add Subscriber** — enter email (your test email)
3. Or import CSV with `email` column

**Important:** Contacts must be **in the list** linked to the campaign. Empty list = no send.

You can also add a subscriber directly in **Campaigns → Edit** when recipient count is 0.

### 3. Campaign
Go to **Campaigns** → **Edit**:
- **Subscriber list:** select your list (must show 1+ recipients)
- **Subject:** required
- **HTML content:** required
- **From email:** should match SMTP domain when possible
- Click **Update**

### 4. Send
Click **Send Now** → confirm  
- Status should become **sent**
- Check **Reports** for sent count
- Check inbox (and spam folder)

### 5. Verify
- **Reports** → Emails Sent / Open rate
- Backend terminal shows email if using console backend
- SMTP Test button if delivery fails

---

## MailWizz guide vs this platform

| MailWizz step | This Email Platform |
|---------------|---------------------|
| Buy MailWizz license | **Not needed** — you built your own app |
| VPS + Nginx + PHP + MySQL | Use `deployment/` configs (Gunicorn + Nginx) when going live |
| MailWizz cron every 1 min | **Celery Beat** (`process_due_scheduled_campaigns` every 60s) |
| SPF / DKIM / DMARC | **Domains** section — add domain, DNS records, Verify |
| Amazon SES / Mailgun | **SMTP** section — add as delivery server |
| Bounce mailbox | Future phase (not built yet) |
| Import + verify list | **Subscribers** → CSV import |
| Test batch | Send to 1–2 test emails first |
| 500k/month scale | SES + VPS + Redis workers in production |

---

## Production setup (real sending at scale)

### Server
```bash
# Ubuntu 24.04 VPS
# Install: Python 3.13, MySQL 8, Redis, Nginx
cd email_platform/backend
pip install -r requirements.txt
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py migrate
gunicorn config.wsgi:application
```

### Celery (required for production sending)
```bash
# Terminal 1 - Worker
celery -A config worker -l info

# Terminal 2 - Beat (scheduled campaigns)
celery -A config beat -l info
```

### Environment (`.env`)
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
CELERY_TASK_ALWAYS_EAGER=False
CELERY_BROKER_URL=redis://127.0.0.1:6379/1
```

### Recommended providers (500k/month)
1. **Amazon SES** — primary (~$50/month at volume)
2. **Mailgun or Brevo** — backup SMTP in **SMTP** section
3. **3 domains:** marketing, tracking, bounce (Domains module for marketing domain)

### DNS (per sending domain)
- **SPF:** `v=spf1 include:amazonses.com ~all` (or provider)
- **DKIM:** from provider / Domains page
- **DMARC:** `v=DMARC1; p=none` → later `p=quarantine`
- **MX** on bounce subdomain (future bounce handler)

### Warm-up
1. Verify list (remove invalid emails)
2. Send 50–200 test emails
3. Check [mail-tester.com](https://www.mail-tester.com)
4. Scale over 2–4 weeks; watch bounce rate in **Reports**

---

## Common errors

| Error | Fix |
|-------|-----|
| Subscriber list is required | Edit campaign → select/create list → Update |
| No active subscribers | Add emails to that list in Subscribers |
| SMTP authentication failed | Check username/password, use app password for Gmail |
| Email in spam | Set up SPF/DKIM/DMARC in Domains |
| Nothing in inbox (dev) | Normal — check backend terminal OR configure SMTP |
| Campaign stuck on sending | Retry Send Now (failed items reset automatically) |

---

## Quick test (your account)

1. **Subscribers** → list `new letter` → add `your-email@gmail.com`
2. **SMTP** → `Datrix Info` → **Set default** → **Test**
3. **Campaigns** → Edit `Hello` → list + subject + HTML → **Update**
4. **Send Now**

Expected: status **sent**, Reports shows 1 sent, email in inbox (if SMTP works).
