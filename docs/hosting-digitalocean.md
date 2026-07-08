# Prod on DigitalOcean (DOKS + managed Postgres + ELK)

The production deploy: the app on a managed Kubernetes cluster (DOKS), Postgres as a
DO Managed Database, monitoring in-cluster, and ELK on a separate droplet. IaC lives
in `infrastructure/digitalocean/`; for local development use `make dev`
(docker-compose).

```
DOKS cluster ── ingress-nginx (DO LoadBalancer) ── cert-manager (Let's Encrypt)
  ├─ web (Next.js)         ┐ namespace warsaw
  ├─ api (FastAPI) + HPA   │  ingress: / → web, /search,/auth,/me,/upcoming,/items,/health → api
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
  - `PG_MONITOR_PASSWORD` (for the read-only DB monitoring role — see *Postgres metrics* under Notes)
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (Alertmanager Telegram alerts — see *Alerting* under Notes)

## Steps (all via the Makefile)

```bash
# 1. Provision: VPC + DOKS + managed Postgres + ELK droplet  (writes .kube/config-do)
make do-infra-up

# 2. Enable pgvector on the managed DB (once; your IP is allowed by the DB firewall)
make do-db-init

# 3. Build + push the images (skip if the ghcr packages are public and already pushed)
make do-images

# 4. Cluster platform: ingress-nginx, cert-manager + issuer, monitoring, fluent-bit
make do-platform

# 5. App secret: fill backend/k8s/secret.yml from secret.example.yml.
#    DATABASE_URL = terraform -chdir=infrastructure/digitalocean output -raw database_url
#    (managed DB; you do NOT apply 10-postgres.yml). Keep ANTHROPIC/VOYAGE/APIFY/
#    TICKETMASTER/GOOGLE_*/SESSION_SECRET. Then:
make do-deploy

# 6. ELK droplet (Elasticsearch + Logstash + Kibana), logs arrive via fluent-bit
make do-elk

# 7. DNS: point WARSAW_DOMAIN at the ingress LoadBalancer IP, then cert-manager issues TLS:
KUBECONFIG=.kube/config-do kubectl get svc -n ingress-nginx   # EXTERNAL-IP of the LB
#   add an A record  <WARSAW_DOMAIN> → <LB IP>  at the registrar
```

First data load (CronJobs run on schedule; trigger one now):
```bash
KUBECONFIG=.kube/config-do kubectl -n warsaw create job --from=cronjob/ingest-places first-places
```

## Access
- App: `https://<WARSAW_DOMAIN>` (TLS by cert-manager).
- Grafana: `https://grafana.<WARSAW_DOMAIN>` — login `admin` / the `GRAFANA_PASSWORD` you set in `.env`.
- Kibana: `http://<elk_public_ip>:5601` (basic auth `kibana` / `KIBANA_PASSWORD`).

## Updating prod (CI/CD)
On push to `main`, `.github/workflows/deploy.yml` runs: **test** → **build+push**
images tagged with the commit SHA → **deploy** (gated behind the `production`
GitHub Environment, so it waits for a manual approval before touching the cluster).

One-time GitHub setup:
- Settings → Environments → `production` with a required reviewer (the approval gate).
- Secret `DIGITALOCEAN_ACCESS_TOKEN` (a CI-only DO token); variable `WARSAW_DOMAIN`.
- ghcr packages public (or an imagePullSecret) so DOKS can pull.
- The `warsaw-secrets` Secret is applied manually once — CI never touches app secrets.

Manual one-off (without CI): `IMAGE_TAG=$(git rev-parse --short HEAD) make do-images do-deploy`.
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
- **Email verification (Resend)**: password registrations get a verification link;
  Google logins are auto-verified. Set `RESEND_API_KEY` and `EMAIL_FROM` (a verified
  sender for your domain, e.g. `Warsaw Events <noreply@transendance.online>`) in the
  app secret (`backend/k8s/secret.yml` + `backend/.env`). Without the key, sending is a
  logged no-op (registration still works, links just aren't delivered). `REQUIRE_EMAIL_VERIFICATION=true`
  refuses password login until verified (default off). ⚠️ This added a `users.email_verified`
  column — a deploy shipping it needs **`make do-db-migrate` first** (the schema-change runbook).
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
```
