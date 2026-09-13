# Local observability stack (Compose)

Runs the **same observability the cloud runs** — metrics, logs, and traces —
next to the app, so the ELK and Prometheus/Grafana DevOps modules can be
demonstrated on a laptop (the DigitalOcean environment is torn down).

## One command

```bash
make stack-up      # build + start the whole stack in the background
make stack-seed    # (optional) load Warsaw places + events into the DB
make stack-down    # stop everything (data kept in named volumes)
make stack-logs    # follow all logs
```

Needs `backend/.env` (API keys) for the API to actually serve — copy
`backend/.env.example` to `backend/.env`. The observability services start
without it.

## What you get

| URL | Service | Login |
|-----|---------|-------|
| http://localhost:3000 | Web (Next.js) | — |
| http://localhost:8000 | API (FastAPI) + `/metrics` | — |
| http://localhost:3001 | **Grafana** (dashboards, Explore, traces) | admin / admin |
| http://localhost:9090 | Prometheus (targets, alerts) | — |
| http://localhost:9093 | Alertmanager | — |
| http://localhost:5601 | **Kibana** (logs) | — |
| http://localhost:3200 | Tempo (traces API; use via Grafana) | — |
| http://localhost:9200 | Elasticsearch | — |

- **Metrics:** Prometheus scrapes `warsaw-api`, `postgres-exporter`, and the
  otel-collector; Grafana ships with two dashboards (*App Overview* — live app
  metrics; *Search Analytics* — the intent_logs dashboard over Postgres).
- **Logs:** every container logs via the Docker `fluentd` driver → Fluent Bit →
  Logstash → Elasticsearch → Kibana (index `warsaw-logs-*`). Create that index
  pattern in Kibana on first use.
- **Traces:** the API pushes OTLP spans → otel-collector → Tempo; open a `/search`
  trace in Grafana → Explore → Tempo to see the per-request waterfall
  (intent → embeddings → retrieval → rerank).

## Parity notes / limitations

- This mirrors the cloud stack with the **delivery mechanism adapted to
  Compose**: DOKS Helm charts and k8s CRDs (ServiceMonitor / PrometheusRule)
  become plain containers with static config (`prometheus.yml`, `rules.yml`,
  Grafana provisioning). Functionally equivalent; not literally the same objects.
- **k8s-only signals have no local equivalent** and stay empty: kube-state-metrics
  and node-exporter panels/alerts (pod restarts, node CPU/mem/disk), and
  cert-manager certificate expiry. Those are cloud-only by nature.
- Elasticsearch heap is set to 512m (vs 2g in the cloud droplet). The full stack
  wants roughly **4–6 GB of RAM** — give Docker enough, or stop it with
  `make stack-down` when you're done.

## Running on Linux / Debian

Works the same (often smoother — native Docker uses host RAM directly), with two
Linux-specific prerequisites:

1. **Elasticsearch needs `vm.max_map_count ≥ 262144`** on the host kernel (Docker
   Desktop sets this inside its VM automatically; native Linux does not):

   ```bash
   sudo sysctl -w vm.max_map_count=262144
   echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-elasticsearch.conf
   ```

   In `single-node` mode ES usually starts without it (dev-mode bootstrap checks
   are non-fatal), but you can hit runtime `map failed` errors as indices grow —
   set it to be safe.

2. **Use Docker Compose v2.24+.** Debian's default `docker.io` + `docker-compose`
   (v1) is too old for this file (`name:`, `env_file: required:false`,
   `depends_on … condition`). Install Docker CE + the compose plugin from
   Docker's official apt repo and use `docker compose` (space), not
   `docker-compose`.

No SELinux relabeling (`:z`) is needed — Debian uses AppArmor, and data lives in
named volumes (not host binds), so there are no volume-permission issues.
