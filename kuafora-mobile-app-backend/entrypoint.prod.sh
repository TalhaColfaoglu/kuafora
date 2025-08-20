#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for PostgreSQL..."

until python - <<'PY'
import os, sys, psycopg2
host = os.getenv("POSTGRES_HOST", "db")
port = int(os.getenv("POSTGRES_PORT", "5432"))
user = os.getenv("POSTGRES_USER")
pwd  = os.getenv("POSTGRES_PASSWORD")
db   = os.getenv("POSTGRES_DB")
try:
    psycopg2.connect(host=host, port=port, user=user, password=pwd, dbname=db, connect_timeout=3)
except Exception:
    sys.exit(1)
PY
do
  echo "Postgres is unavailable - sleeping"
  sleep 2
done

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --worker-class gthread \
  --threads 4 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -