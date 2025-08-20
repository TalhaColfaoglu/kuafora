DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = current_setting('BACKEND_USER')) THEN
      EXECUTE format('CREATE USER %I WITH PASSWORD %L;', current_setting('BACKEND_USER'), current_setting('BACKEND_PASSWORD'));
   END IF;
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = current_setting('BACKEND_DB')) THEN
      EXECUTE format('CREATE DATABASE %I OWNER %I;', current_setting('BACKEND_DB'), current_setting('BACKEND_USER'));
   END IF;

   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = current_setting('WEBSITE_USER')) THEN
      EXECUTE format('CREATE USER %I WITH PASSWORD %L;', current_setting('WEBSITE_USER'), current_setting('WEBSITE_PASSWORD'));
   END IF;
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = current_setting('WEBSITE_DB')) THEN
      EXECUTE format('CREATE DATABASE %I OWNER %I;', current_setting('WEBSITE_DB'), current_setting('WEBSITE_USER'));
   END IF;
END
$$;
