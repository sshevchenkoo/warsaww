-- Read-only monitoring DB role for prometheus-postgres-exporter.
-- Run as admin (doadmin) via `make do-db-monitor-role`, which passes the
-- password as the psql variable :pw (from PG_MONITOR_PASSWORD). Idempotent.
--
-- The exporter only reads cluster stats. The three metrics we actually use —
-- pg_up, pg_stat_database_numbackends, pg_settings_max_connections — are
-- readable by any LOGIN role, so this role needs no elevated grant. We do NOT
-- grant pg_monitor: on DO managed Postgres `doadmin` is not a superuser and
-- lacks ADMIN on pg_monitor, so `GRANT pg_monitor` fails ("permission denied to
-- grant role"). A bare login role keeps collection off a privileged role (same
-- spirit as warsaw_app) and is all the exporter needs here.

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
