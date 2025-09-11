#!/usr/bin/env sh
set -e

echo "[website] Collecting static files (clear old ones)..."
python manage.py collectstatic --noinput --clear

echo "[website] Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:8001 --workers 3 --worker-class gevent --worker-connections 1000 --max-requests 1000 --max-requests-jitter 100 --timeout 30 --keep-alive 5 config.wsgi:application


