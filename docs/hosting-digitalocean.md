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
- `infrastructure/digitalocean/terraform.tfvars` (copy from `.example`):
  `do_token`, `ssh_public_key` (e.g. `cat ~/.ssh/hetzner_warsaw.pub`), `admin_ip` (`curl ifconfig.me` + `/32`).
- `.env` (repo root): `GITHUB_USER`, `GITHUB_TOKEN`, `ACME_EMAIL`, `WARSAW_DOMAIN`, `KIBANA_PASSWORD`.

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
- Grafana: `kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80` (admin pass: `kubectl -n monitoring get secret monitoring-grafana -o jsonpath='{.data.admin-password}' | base64 -d`).
- Kibana: `http://<elk_public_ip>:5601` (basic auth `kibana` / `KIBANA_PASSWORD`).

## Notes
- **Cost** (~): 2× s-2vcpu-4gb nodes ≈ $48, LoadBalancer ≈ $12, managed PG ≈ $15, ELK
  droplet (s-4vcpu-8gb) ≈ $48 → ~$120/mo. The $200 student credit covers ~7 weeks.
  Shrink node/elk sizes to stretch it.
- **Images**: cluster pulls from `ghcr.io/<user>/warsaw-{events,web}`. Make those
  packages public, or add an imagePullSecret to the `warsaw` namespace.
- **TLS**: `40-ingress.yml` already carries `cert-manager.io/cluster-issuer: letsencrypt-prod`
  and SSE-safe annotations (proxy-buffering off, long timeouts).
- **Teardown** (stop the bill): `make do-infra-down` (destroys cluster, DB, droplet, VPC).
```
