#!/bin/sh
set -e

# Create roles if not exists (allowed inside DO), and ensure passwords
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$BACKEND_USER') THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L;', '$BACKEND_USER', '$BACKEND_PASSWORD');
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$WEBSITE_USER') THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L;', '$WEBSITE_USER', '$WEBSITE_PASSWORD');
  END IF;
END
\$\$;

ALTER ROLE "$BACKEND_USER" WITH PASSWORD '$BACKEND_PASSWORD';
ALTER ROLE "$WEBSITE_USER" WITH PASSWORD '$WEBSITE_PASSWORD';
EOSQL

# Create databases if not exists (cannot run inside DO)
if ! psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_database WHERE datname = '$BACKEND_DB'" | grep -q 1; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "CREATE DATABASE \"$BACKEND_DB\" OWNER \"$BACKEND_USER\";"
fi

if ! psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_database WHERE datname = '$WEBSITE_DB'" | grep -q 1; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "CREATE DATABASE \"$WEBSITE_DB\" OWNER \"$WEBSITE_USER\";"
fi


