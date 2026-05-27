# ft_transcendence — Infrastructure

DevOps module for ft_transcendence. Provisions a full production stack on Hetzner Cloud using Terraform, Ansible, and k3s — launched with a single command.

## Architecture

```
                        Internet
                            │
                     ┌──────▼──────┐
                     │  Hetzner    │
                     │  Firewall   │
                     └──────┬──────┘
                            │ :80 / :443
               ┌────────────▼────────────┐
               │     k3s Cluster         │
               │                         │
               │  ┌─────────────────┐    │
               │  │  Nginx Ingress  │    │
               │  └────────┬────────┘    │
               │           │             │
               │  ┌────────▼────────┐    │
               │  │    backend      │    │   ┌──────────────────┐
               │  │  (Django x2)   │────┼──►│  PostgreSQL VM   │
               │  └────────┬────────┘    │   │  10.0.1.20:5432  │
               │           │             │   └──────────────────┘
               │  ┌────────▼────────┐    │
               │  │     Redis       │    │
               │  └─────────────────┘    │
               │                         │
               │  monitoring namespace:  │
               │  Prometheus  Grafana    │
               │  Tempo  OTel Collector  │
               │  Fluent Bit (DaemonSet) │
               └─────────────────────────┘
                            │ logs
               ┌────────────▼────────────┐
               │       ELK VM            │
               │  Elasticsearch          │
               │  Logstash               │
               │  Kibana (nginx auth)    │
               └─────────────────────────┘
```

### VMs

| Name | Type | Private IP | Role |
|---|---|---|---|
| transcendence-master | cx22 | 10.0.1.10 | k3s master |
| transcendence-worker-1 | cx22 | 10.0.1.11 | k3s worker |
| transcendence-worker-2 | cx22 | 10.0.1.12 | k3s worker |
| transcendence-postgres | cx22 | 10.0.1.20 | PostgreSQL |
| transcendence-elk | cx32 | 10.0.1.30 | Elasticsearch + Logstash + Kibana |

---

## Subject Modules Implemented

### Major — Infrastructure: ELK Stack
- **Elasticsearch** stores and indexes all k8s container logs
- **Logstash** receives logs from Fluent Bit (TCP/JSON), transforms and ships to ES
- **Kibana** — web UI at `http://<elk-ip>:5601` protected by nginx basic auth
- **ILM policy** — logs automatically deleted after 30 days
- **Secure access** — Kibana behind nginx htpasswd, Logstash port only open to private network

### Major — Monitoring: Prometheus + Grafana
- **Prometheus** scrapes metrics from k3s nodes, k8s cluster state, and PostgreSQL
- **Exporters**: node-exporter (all k3s nodes), kube-state-metrics, postgres_exporter
- **Grafana** at `https://grafana.DOMAIN` with HTTPS (cert-manager) and password auth
- **Custom dashboard** — Cluster Overview (pods, CPU/RAM per node, DB connections, restarts)
- **Alerting rules** — CrashLoop, NodeHighMemory, NodeHighCPU, DiskPressure, PostgresDown
- **Tempo** — distributed tracing backend (receives OTLP from OTel Collector)
- **OTel Collector** — receives traces/metrics from Django app via OTLP (:4317/:4318)
- **Fluent Bit** — DaemonSet that ships all container logs to ELK

### Minor — Health Check + Backup
- **`/health/`** endpoint — checks DB and Redis, returns JSON status
- **k8s probes** — readiness and liveness probes hit `/health/` on every pod
- **Automated backups** — daily pg_dump at 2:00 AM, 7-day retention, gzipped
- **Disaster recovery** — restore script with confirmation prompt

---

## Prerequisites

- [Terraform](https://www.terraform.io/) >= 1.5
- [Ansible](https://www.ansible.com/) >= 2.14 + `hetzner.hcloud` collection
- `kubectl`, `ssh`, `scp`, `envsubst` available in PATH
- Hetzner Cloud account with API token (Read & Write)
- Domain with DNS pointed to Hetzner (for TLS via Let's Encrypt)

```bash
# Install Ansible Hetzner collection (once)
ansible-galaxy collection install hetzner.hcloud
```

---

## Quick Start

### 1. Clone and configure

```bash
git clone <repo>
cd ft_transcendence
cp .env.example .env
# Fill in all values in .env
```

### 2. Launch infrastructure (do this before evaluation day)

```bash
make keys          # generate SSH key pair in .ssh/
make infra-up      # create 5 VMs on Hetzner (~2 min)
make configure     # install k3s, PostgreSQL, ELK, monitoring via Ansible (~15 min)
make get-kubeconfig  # download kubeconfig from master
```

### 3. Deploy the application

```bash
make full-deploy   # build Docker image → push to ghcr.io → deploy to k3s
```

### 4. Verify everything works

```bash
# Site
curl https://DOMAIN/health/
# {"status": "ok", "db": "ok", "redis": "ok"}

# Grafana
open https://grafana.DOMAIN
# login: admin / GRAFANA_PASSWORD from .env

# Kibana
open http://<elk-public-ip>:5601
# login: kibana / KIBANA_PASSWORD from .env

# Prometheus targets
kubectl --kubeconfig .kube/config -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090
open http://localhost:9090/targets
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all values. The file is gitignored and never committed.

```bash
# Hetzner
HCLOUD_TOKEN=           # API token from hetzner.com → Security → API Tokens
YOUR_SSH_IP=            # your public IP (curl ifconfig.me) — SSH is locked to this IP

# GitHub Container Registry
GITHUB_USER=            # your GitHub username
GITHUB_TOKEN=           # Personal Access Token with packages:write

# Domain & TLS
DOMAIN=                 # your domain, e.g. transcendence.example.com
LETSENCRYPT_EMAIL=      # email for Let's Encrypt certificate notifications

# Application secrets
POSTGRES_PASSWORD=      # strong random password for PostgreSQL
DJANGO_SECRET_KEY=      # 50-char random string for Django

# Monitoring
GRAFANA_PASSWORD=       # Grafana admin password
KIBANA_PASSWORD=        # Kibana basic auth password
```

---

## Make Targets Reference

```
Infrastructure:
  make keys             generate SSH keys in .ssh/
  make infra-up         create VMs on Hetzner Cloud
  make infra-plan       show Terraform plan without applying
  make infra-down       destroy all VMs
  make configure        provision all servers with Ansible
  make ping             check Ansible can reach all hosts

Docker image:
  make build            build production image
  make push             push to ghcr.io
  make build-push       build + push

Kubernetes:
  make get-kubeconfig   download kubeconfig from master to .kube/config
  make create-secrets   create k8s Secret from .env values
  make deploy           apply all k8s manifests

Database:
  make db-backup        run on-demand backup on postgres VM
  make db-backup-list   list available backups
  make db-restore BACKUP=<path>  restore from backup file

Full pipelines:
  make all              keys → infra-up → configure
  make full-deploy      build-push → create-secrets → deploy
  make fclean           destroy VMs + remove .ssh/ and .kube/
```

---

## Monitoring

### Grafana
URL: `https://grafana.DOMAIN`
Login: `admin` / `GRAFANA_PASSWORD`

Included dashboards:
- **Transcendence — Cluster Overview** — pods, CPU/RAM per node, DB connections, container restarts
- **Kubernetes / Compute Resources** — default kube-prometheus-stack dashboards

### Kibana
URL: `http://<elk-public-ip>:5601` (port open to `YOUR_SSH_IP` only)
Login: `kibana` / `KIBANA_PASSWORD`

Index pattern: `k8s-logs-*`
Log retention: 30 days (ILM policy)

### Application traces (Tempo)
Accessible via Grafana → Explore → Tempo datasource.
Django app must be instrumented with OpenTelemetry SDK pointing to:
```
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector-opentelemetry-collector.monitoring:4317
```

### Alert rules
Alerts fire to AlertManager (no external notification configured by default):
- `PodCrashLooping` — container restarts > 1/min for 5 min
- `PodNotReady` — pod not ready for 5 min
- `DeploymentReplicasMismatch` — desired != available replicas
- `NodeHighMemory` — RAM > 85%
- `NodeHighCPU` — CPU > 80% for 10 min
- `NodeDiskPressure` — disk < 15%
- `PostgresDown` — postgres_exporter reports pg_up == 0
- `PostgresTooManyConnections` — connections > 80% of max_connections

---

## Backup & Disaster Recovery

### Automated backups
Daily pg_dump runs at 2:00 AM on the postgres VM.
Backups stored at `/var/backups/postgresql/` as `transcendence_YYYYMMDD_HHMMSS.sql.gz`.
Retention: 7 days.

```bash
# Check backup status
make db-backup-list

# Run manual backup immediately
make db-backup
```

### Restore procedure

```bash
# 1. List available backups
make db-backup-list

# 2. Restore (stops active connections, drops DB, recreates and imports)
make db-restore BACKUP=/var/backups/postgresql/transcendence_20240101_020000.sql.gz
```

The restore script prompts for confirmation before dropping the database.

---

## Health Check

`GET /health/` returns the status of the application and its dependencies:

```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok"
}
```

Returns HTTP 200 when healthy, HTTP 500 when any dependency is down.
k8s readiness and liveness probes use this endpoint — unhealthy pods are automatically removed from the load balancer and restarted.

---

## Data Flow

```
Logs:    k8s containers → Fluent Bit → Logstash (10.0.1.30:5000) → Elasticsearch → Kibana
Metrics: k3s nodes      → node-exporter → Prometheus → Grafana
         PostgreSQL VM  → postgres_exporter (10.0.1.20:9187) → Prometheus → Grafana
         Django app     → OTel SDK → OTel Collector → Prometheus (metrics) / Tempo (traces)
```
