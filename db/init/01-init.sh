#!/bin/sh
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  DO \$\$
  BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$BACKEND_USER') THEN
      EXECUTE format('CREATE USER %I WITH PASSWORD %L;', '$BACKEND_USER', '$BACKEND_PASSWORD');
    END IF;
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = '$BACKEND_DB') THEN
      EXECUTE format('CREATE DATABASE %I OWNER %I;', '$BACKEND_DB', '$BACKEND_USER');
    END IF;

    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$WEBSITE_USER') THEN
      EXECUTE format('CREATE USER %I WITH PASSWORD %L;', '$WEBSITE_USER', '$WEBSITE_PASSWORD');
    END IF;
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = '$WEBSITE_DB') THEN
      EXECUTE format('CREATE DATABASE %I OWNER %I;', '$WEBSITE_DB', '$WEBSITE_USER');
    END IF;
  END
  \$\$;
EOSQL


