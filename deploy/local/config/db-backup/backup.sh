#!/bin/sh
# Dump the app database to /backups — bind-mounted to deploy/local/backups/ on
# the host, outside every Docker volume, so a dump survives `down -v` and a lost
# pgdata volume. Run nightly by crond in the `db-backup` service and on demand by
# `make stack-db-backup`. Dumps older than BACKUP_KEEP_DAYS are pruned.
set -eu

# crond starts jobs with an empty environment; the service saves PG* and
# BACKUP_* here at startup.
[ -f /etc/backup.env ] && . /etc/backup.env

f=/backups/events_$(date -u +%Y%m%d_%H%M%S).dump
# Write under a temporary name first, so a restore can never pick up a dump
# that is still being written (or was cut short).
pg_dump -Fc -f "$f.part"
mv "$f.part" "$f"
chmod 644 "$f"
find /backups -name 'events_*.dump' -mtime +"${BACKUP_KEEP_DAYS:-7}" -delete

echo "backup ok: deploy/local/backups/$(basename "$f") ($(du -h "$f" | cut -f1))"
