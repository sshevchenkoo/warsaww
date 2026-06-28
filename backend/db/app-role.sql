-- Least-privilege runtime DB role for the app (audit #4).
-- Run as admin (doadmin) via `make do-db-role`, which passes the password as
-- the psql variable :pw (from WARSAW_APP_DB_PASSWORD). Idempotent.
--
-- The app currently connects as `doadmin` (full cluster admin). This role can
-- only read/write the app's own tables — no DDL, no CREATE ROLE/DB — so a
-- compromise can't drop the schema, create backdoor roles, or touch other DBs.
-- Schema management moves to the admin-run `make do-db-migrate` step.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'warsaw_app') THEN
    CREATE ROLE warsaw_app LOGIN;
  END IF;
END
$$;

-- (Re)set the password each run so rotation is just re-running this target.
ALTER ROLE warsaw_app PASSWORD :'pw';

-- Connect + see the schema, but nothing creatable.
GRANT CONNECT ON DATABASE events TO warsaw_app;
GRANT USAGE ON SCHEMA public TO warsaw_app;

-- DML on existing tables/sequences (no DDL, no TRUNCATE).
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO warsaw_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO warsaw_app;

-- Tables/sequences created later by the migrate step (run as doadmin) are
-- granted to the app role automatically.
ALTER DEFAULT PRIVILEGES FOR ROLE doadmin IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO warsaw_app;
ALTER DEFAULT PRIVILEGES FOR ROLE doadmin IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO warsaw_app;
