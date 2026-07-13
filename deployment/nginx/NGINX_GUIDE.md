# Nginx Deployment Guide — email_platform

## Prerequisites

- Ubuntu 24.04 LTS
- Django application running via Gunicorn on `127.0.0.1:8000`
- Domain DNS pointing to the server

## 1. Install Nginx

```bash
sudo apt update
sudo apt install -y nginx
```

## 2. Deploy Application Files

```bash
sudo mkdir -p /var/www/email_platform
sudo chown -R $USER:www-data /var/www/email_platform
```

Copy or clone the project to `/var/www/email_platform`.

## 3. Collect Static Files

```bash
cd /var/www/email_platform/backend
source /var/www/email_platform/.venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py collectstatic --noinput
```

## 4. Install Site Configuration

```bash
sudo cp /var/www/email_platform/deployment/nginx/email_platform.conf \
    /etc/nginx/sites-available/email_platform

sudo ln -sf /etc/nginx/sites-available/email_platform \
    /etc/nginx/sites-enabled/email_platform

sudo rm -f /etc/nginx/sites-enabled/default
```

Edit `/etc/nginx/sites-available/email_platform` and replace `your-domain.com` with your domain.

## 5. Test and Reload

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl enable nginx
```

## 6. SSL with Let's Encrypt (Recommended)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

After SSL is active, uncomment the HTTPS server block in the Nginx config if using manual SSL configuration.

## 7. Frontend (SPA)

Serve the built React app from Nginx by adding a location block:

```nginx
location / {
    root /var/www/email_platform/frontend/dist;
    try_files $uri $uri/ /index.html;
}
```

For API-only proxy setups, keep the existing `proxy_pass` configuration for `/api/` routes in a future phase.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 502 Bad Gateway | Verify Gunicorn is running: `sudo supervisorctl status` |
| Static files 404 | Re-run `collectstatic`, check `alias` paths |
| Permission denied | `sudo chown -R www-data:www-data staticfiles media` |
