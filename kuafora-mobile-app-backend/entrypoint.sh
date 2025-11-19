#!/usr/bin/env bash
set -euo pipefail

# Wait for Postgres
echo "Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
until python - <<PY
import os,sys,psycopg2
host=os.environ.get('POSTGRES_HOST','db')
port=int(os.environ.get('POSTGRES_PORT','5432'))
user=os.environ.get('POSTGRES_USER','postgres')
password=os.environ.get('POSTGRES_PASSWORD','postgres')
db=os.environ.get('POSTGRES_DB','postgres')
try:
    psycopg2.connect(host=host, port=port, user=user, password=password, dbname=db)
except Exception as e:
    sys.exit(1)
PY
do
  echo "Postgres is unavailable - sleeping"
  sleep 1
done

python manage.py collectstatic --noinput
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# Generate OpenAPI schema file for Swagger UI to consume
mkdir -p staticfiles
python manage.py spectacular --file staticfiles/openapi.yaml || true

if [ "${DEBUG:-0}" = "1" ]; then
  python manage.py runserver 0.0.0.0:8000
else
  gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
fi


