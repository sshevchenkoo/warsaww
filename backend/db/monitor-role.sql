-- Read-only monitoring DB role for prometheus-postgres-exporter.
-- Run as admin (doadmin) via `make do-db-monitor-role`, which passes the
-- password as the psql variable :pw (from PG_MONITOR_PASSWORD). Idempotent.
--
-- The exporter needs to read pg_stat_* / pg_settings only. `pg_monitor` is a
-- predefined, read-only role (available on DO managed Postgres) that grants
-- exactly that visibility — no DML, no DDL, no CREATE ROLE/DB. It exists purely
-- so metrics collection never runs as a privileged role (same spirit as
-- warsaw_app in app-role.sql).

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'warsaw_monitor') THEN
    CREATE ROLE warsaw_monitor LOGIN;
  END IF;
END
$$;

-- (Re)set the password each run so rotation is just re-running this target.
ALTER ROLE warsaw_monitor LOGIN PASSWORD :'pw';

-- Connect to the app DB and read cluster stats — nothing else.
GRANT CONNECT ON DATABASE events TO warsaw_monitor;
GRANT pg_monitor TO warsaw_monitor;
