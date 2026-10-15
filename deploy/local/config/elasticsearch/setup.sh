#!/bin/sh
# One-shot Elasticsearch setup for the local stack (the `elk-setup` service):
# log retention + archiving for the daily warsaw-logs-* indices, mirroring the
# cloud ILM policy in deploy/cloud/ansible/roles/elk. Every call is a PUT, so it
# is idempotent and simply re-applies on each `make stack-up`.
#
#   archive — SLM snapshots warsaw-logs-* every night into the fs repository on
#             the es-snapshots volume; snapshots are kept LOG_ARCHIVE_DAYS.
#   retain  — ILM deletes an index LOG_RETENTION_DAYS after it was created, but
#             only once a snapshot holds it (wait_for_snapshot), so no log line
#             leaves Elasticsearch without being archived first.
set -eu

ES=http://elasticsearch:9200
REPO_DIR=/usr/share/elasticsearch/snapshots
RETENTION_DAYS=${LOG_RETENTION_DAYS:-30}
ARCHIVE_DAYS=${LOG_ARCHIVE_DAYS:-365}

# The named volume is created root-owned; Elasticsearch runs as uid 1000 and
# must be able to write the repository before it can be registered.
chown 1000:0 "$REPO_DIR"

put() {  # put <path> <json body>
  printf 'PUT %s → ' "$1"
  curl -sSf -X PUT "$ES/$1" -H 'Content-Type: application/json' -d "$2"
  echo
}

put _snapshot/warsaw-logs-archive \
  "{\"type\":\"fs\",\"settings\":{\"location\":\"$REPO_DIR\",\"compress\":true}}"

# 01:30 UTC daily. Two runs on one day (e.g. a manual `make stack-logs-archive`)
# get distinct names: SLM appends a unique suffix to every snapshot.
put _slm/policy/warsaw-logs-nightly "{
  \"schedule\": \"0 30 1 * * ?\",
  \"name\": \"<warsaw-logs-{now/d}>\",
  \"repository\": \"warsaw-logs-archive\",
  \"config\": {\"indices\": [\"warsaw-logs-*\"], \"include_global_state\": false, \"ignore_unavailable\": true},
  \"retention\": {\"expire_after\": \"${ARCHIVE_DAYS}d\", \"min_count\": 1, \"max_count\": 500}
}"

put _ilm/policy/warsaw-logs-policy "{\"policy\":{\"phases\":{\"delete\":{
  \"min_age\": \"${RETENTION_DAYS}d\",
  \"actions\": {\"wait_for_snapshot\": {\"policy\": \"warsaw-logs-nightly\"}, \"delete\": {}}
}}}}"

# New daily indices pick the policy up from the template; the ones that already
# exist get it set directly.
put _index_template/warsaw-logs \
  '{"index_patterns":["warsaw-logs-*"],"template":{"settings":{"index.lifecycle.name":"warsaw-logs-policy"}}}'
put 'warsaw-logs-*/_settings' '{"index.lifecycle.name":"warsaw-logs-policy"}'

echo "log retention: delete after ${RETENTION_DAYS}d once archived; archive kept ${ARCHIVE_DAYS}d"
