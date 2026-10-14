# Prod on DigitalOcean (DOKS + managed Postgres + ELK)

The production deploy: the app on a managed Kubernetes cluster (DOKS), Postgres as a
DO Managed Database, monitoring in-cluster, and ELK on a separate droplet. IaC lives
in `deploy/cloud/terraform/`; for local development use `make dev`
(docker-compose).

```
DOKS cluster ── ingress-nginx (DO LoadBalancer) ── cert-manager (Let's Encrypt)
  ├─ web (Next.js)         ┐ namespace warsaw
  ├─ api (FastAPI) + HPA   │  ingress: / → web, API prefixes → api (deployment.md)
  ├─ redis                 ┘
  ├─ CronJobs (ingestion)
  ├─ kube-prometheus-stack (Grafana/Prometheus)   namespace monitoring
  └─ fluent-bit ──► (VPC) ──► ELK droplet (Logstash:5000 → Elasticsearch → Kibana:5601)
api ──► (VPC) ──► DO Managed Postgres 16 (pgvector)
```

## Prerequisites
- CLIs: `terraform`, `kubectl`, `helm`, `ansible`, `doctl` (optional), `psql`, `envsubst`.
- A DO API token, a domain, and a GitHub token (ghcr) — or make the ghcr packages public.
- An SSH key: `make keys` (creates `.ssh/id_ed25519`; used for the ELK droplet).
- `.env` (repo root) — all Terraform/DO config lives here, no `terraform.tfvars`:
  - `DIGITALOCEAN_TOKEN` (the provider reads this), `TF_VAR_ssh_public_key` (`cat .ssh/id_ed25519.pub`), `TF_VAR_admin_ip` (`curl ifconfig.me` + `/32`)
  - `GITHUB_USER`, `GITHUB_TOKEN`, `ACME_EMAIL`, `WARSAW_DOMAIN`, `GRAFANA_PASSWORD`, `KIBANA_PASSWORD`
  - `WARSAW_APP_DB_PASSWORD` (the least-privilege `warsaw_app` role the API connects as)
  - `PG_MONITOR_PASSWORD` (for the read-only DB monitoring role — see *Postgres metrics* under Notes)
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (Alertmanager Telegram alerts — see *Alerting* under Notes)

## Steps (all via the Makefile)

```bash
# 1. Provision: VPC + DOKS + managed Postgres + ELK droplet, then save the kubeconfig
make do-infra-up
make do-kubeconfig     # writes .kube/config-do; every later step uses it

# 2. Prepare the managed DB (idempotent; your IP is allowed by the DB firewall)
make do-db-init        # enable vector + pg_trgm
make do-db-role        # least-privilege app role warsaw_app
make do-db-monitor-role
make do-db-migrate     # create/upgrade the schema as admin

# 3. Build + push the images (skip if the ghcr packages are public and already pushed)
make do-images

# 4. Cluster platform: ingress-nginx, cert-manager + issuer, monitoring, fluent-bit
make do-platform

# 5. App secret: fill deploy/cloud/k8s/secret.yml from secret.example.yml
#    (DATABASE_URL uses the warsaw_app role; keys: deployment.md §2). do-deploy applies it:
make do-deploy

# 6. ELK droplet (Elasticsearch + Logstash + Kibana), logs arrive via fluent-bit
make do-elk

# 7. DNS: point WARSAW_DOMAIN at the ingress LoadBalancer IP, then cert-manager issues TLS:
KUBECONFIG=.kube/config-do kubectl get svc -n ingress-nginx   # EXTERNAL-IP of the LB
#   add an A record  <WARSAW_DOMAIN> → <LB IP>  at the registrar
```

First data load: trigger the CronJobs by hand — [deployment.md](deployment.md) §4.

## Access
- App: `https://<WARSAW_DOMAIN>` (TLS by cert-manager).
- Grafana: `https://grafana.<WARSAW_DOMAIN>` — login `admin` / the `GRAFANA_PASSWORD` you set in `.env`.
- Kibana: `http://<elk_public_ip>:5601` (basic auth `kibana` / `KIBANA_PASSWORD`).

## Updating prod
Deployment is manual (no CI). After a change:

```bash
IMAGE_TAG=$(git rev-parse --short HEAD) make do-images do-deploy
```
`do-images` builds + pushes the API/web images to GHCR tagged by the commit SHA
(immutable); `do-deploy` renders and `kubectl apply`s `deploy/cloud/k8s/*` — the SHA
tag makes the rollout self-roll. The `warsaw-secrets` Secret comes from the gitignored
`deploy/cloud/k8s/secret.yml`, re-applied by every `do-deploy`; run `make do-platform` / `make do-elk`
only when the platform charts or the ELK host change. ghcr packages must be public (or
add an imagePullSecret) so DOKS can pull.
Rollback: `kubectl -n warsaw rollout undo deploy/api` or redeploy an older `IMAGE_TAG`.

## Notes
- **Cost** (~): 2× s-2vcpu-4gb nodes ≈ $48, LoadBalancer ≈ $12, managed PG ≈ $15, ELK
  droplet (s-4vcpu-8gb) ≈ $48 → ~$120/mo. The $200 student credit covers ~7 weeks.
  Shrink node/elk sizes to stretch it.
- **Images**: cluster pulls from `ghcr.io/<user>/warsaw-{events,web}`. Make those
  packages public, or add an imagePullSecret to the `warsaw` namespace.
- **TLS**: `40-ingress.yml` already carries `cert-manager.io/cluster-issuer: letsencrypt-prod`
  and SSE-safe annotations (proxy-buffering off, long timeouts).
- **Alerting (Telegram)**: DORMANT by default — Alertmanager routes to `null`, and
  the Telegram receiver is a commented template in `kube-prometheus-stack-values.yaml`,
  so `do-platform` is safe without any Telegram config. To ACTIVATE: create a bot via
  [@BotFather](https://t.me/BotFather), get your `chat_id` (message the bot, then
  `https://api.telegram.org/bot<TOKEN>/getUpdates`; group ids are negative), set
  `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in `.env`, **uncomment the `telegram`
  receiver and flip the route to it** in the values file, then `make do-platform`
  (envsubst injects them — no secret in git). ⚠️ Don't uncomment without setting both
  vars: an empty bot_token makes the Alertmanager config invalid.
- **Email and the search gate**: `RESEND_API_KEY` / `EMAIL_FROM` (a verified sender
  for your domain) go in the app secret; `REQUIRE_VERIFIED_EMAIL_TO_SEARCH` and
  `REQUIRE_EMAIL_VERIFICATION` are described in [auth.md](auth.md#config). A deploy
  that adds columns needs **`make do-db-migrate` first** ([deployment.md](deployment.md) §3).
- **Postgres metrics**: DO Postgres is managed (no in-cluster instance), so a
  `prometheus-postgres-exporter` connects out to it and backs the Grafana
  PostgreSQL panels + `PostgresDown` / `PostgresTooManyConnections` alerts.
  `make do-platform` installs the exporter; two one-time admin steps light it up
  (both idempotent, run from a host whose IP the DB firewall trusts):
  ```bash
  # a) read-only monitoring role (pg_monitor); set PG_MONITOR_PASSWORD in .env first
  make do-db-monitor-role
  # b) the DSN secret the exporter reads. Derive host/port from the app's working
  #    DATABASE_URL (strip the +psycopg dialect, swap in the monitor creds):
  KUBECONFIG=.kube/config-do kubectl -n monitoring create secret generic postgres-exporter-dsn \
    --from-literal=DATA_SOURCE_NAME='postgresql://warsaw_monitor:<PG_MONITOR_PASSWORD>@<host>:<port>/events?sslmode=require'
  KUBECONFIG=.kube/config-do kubectl -n monitoring rollout restart deploy/prometheus-postgres-exporter
  ```
  Until both exist the exporter simply reports `pg_up=0` (harmless). Verify:
  `kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090` →
  Status → Targets → the `postgres` job is UP.
- **Teardown** (stop the bill): `make do-infra-down` (destroys cluster, DB, droplet, VPC).
