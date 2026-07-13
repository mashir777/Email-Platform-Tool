# Supervisor Configuration Guide — email_platform

## Prerequisites

- Ubuntu 24.04 LTS
- Python virtual environment at `/var/www/email_platform/.venv`
- Redis and MySQL running
- Application deployed to `/var/www/email_platform`

## 1. Install Supervisor

```bash
sudo apt update
sudo apt install -y supervisor
```

## 2. Install Configuration

```bash
sudo cp /var/www/email_platform/deployment/supervisor/email_platform.conf \
    /etc/supervisor/conf.d/email_platform.conf
```

Adjust paths in the config if your deployment directory differs.

## 3. Create Log Directory

```bash
sudo mkdir -p /var/log/supervisor
sudo touch /var/log/supervisor/email_platform_gunicorn.log
sudo touch /var/log/supervisor/email_platform_celery_worker.log
sudo touch /var/log/supervisor/email_platform_celery_beat.log
sudo chown www-data:www-data /var/log/supervisor/email_platform_*.log
```

## 4. Set Permissions

```bash
sudo chown -R www-data:www-data /var/www/email_platform/backend/media
sudo chown -R www-data:www-data /var/www/email_platform/backend/logs
sudo chown -R www-data:www-data /var/www/email_platform/backend/staticfiles
```

## 5. Load and Start Services

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start email_platform:*
```

## 6. Verify Status

```bash
sudo supervisorctl status
```

Expected output:

```
email_platform:email_platform_celery_beat    RUNNING
email_platform:email_platform_celery_worker RUNNING
email_platform:email_platform_gunicorn      RUNNING
```

## Common Commands

```bash
# Restart all services
sudo supervisorctl restart email_platform:*

# Restart individual service
sudo supervisorctl restart email_platform:email_platform_gunicorn

# Tail logs
sudo tail -f /var/log/supervisor/email_platform_gunicorn.log
```

## Boot on Startup

Supervisor is enabled automatically on Ubuntu when installed:

```bash
sudo systemctl enable supervisor
sudo systemctl start supervisor
```

## After Code Deploy

```bash
cd /var/www/email_platform
git pull
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo supervisorctl restart email_platform:*
```
