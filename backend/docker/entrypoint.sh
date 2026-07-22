#!/bin/sh
set -e

echo "Waiting for Redis..."
python - <<'PY'
import os, time
import redis

url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
for i in range(30):
    try:
        redis.from_url(url).ping()
        print("Redis is ready.")
        break
    except Exception as exc:
        print(f"Redis not ready ({exc}), retry {i + 1}/30...")
        time.sleep(2)
else:
    raise SystemExit("Redis did not become ready in time.")
PY

if [ -n "${DATABASE_URL:-}" ]; then
  echo "Waiting for Postgres..."
  python - <<'PY'
import os, time
from urllib.parse import urlparse, unquote
import psycopg

u = urlparse(os.environ["DATABASE_URL"])
conninfo = {
    "dbname": (u.path or "/").lstrip("/") or "email_platform",
    "user": unquote(u.username or ""),
    "password": unquote(u.password or ""),
    "host": u.hostname or "db",
    "port": u.port or 5432,
}
for i in range(40):
    try:
        with psycopg.connect(**conninfo) as conn:
            conn.execute("SELECT 1")
        print("Postgres is ready.")
        break
    except Exception as exc:
        print(f"Postgres not ready ({exc}), retry {i + 1}/40...")
        time.sleep(2)
else:
    raise SystemExit("Postgres did not become ready in time.")
PY
fi

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Running migrations..."
  python manage.py migrate --noinput
fi

if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput
fi

exec "$@"
