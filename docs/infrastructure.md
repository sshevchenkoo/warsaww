# Infrastructure — the self-hosted platform

DevOps platform (originally the **ft_transcendence** module) that provisions a
full production stack on Hetzner Cloud with Terraform, Ansible and k3s —
launched with a single command. The Warsaw-events application and the original
ft_transcendence Django service both run on top of it.

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
               │  │   application   │    │   ┌──────────────────┐
               │  │   pods (x2)     │────┼──►│  PostgreSQL VM   │
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

## Platform modules

### Logging — ELK Stack
- **Elasticsearch** stores and indexes all k8s container logs.
- **Logstash** receives logs from Fluent Bit (TCP/JSON), transforms and ships to ES.
- **Kibana** — web UI at `http://<elk-ip>:5601` protected by nginx basic auth.
- **ILM policy** — logs automatically deleted after 30 days.
- **Secure access** — Kibana behind nginx htpasswd, Logstash port only open to the private network.

### Monitoring — Prometheus + Grafana
- **Prometheus** scrapes metrics from k3s nodes, k8s cluster state, and PostgreSQL.
- **Exporters**: node-exporter (all k3s nodes), kube-state-metrics, postgres_exporter.
- **Grafana** at `https://grafana.DOMAIN` with HTTPS (cert-manager) and password auth.
- **Custom dashboard** — Cluster Overview (pods, CPU/RAM per node, DB connections, restarts).
- **Alerting rules** — CrashLoop, NodeHighMemory, NodeHighCPU, DiskPressure, PostgresDown.
- **Tempo** — distributed tracing backend (receives OTLP from the OTel Collector).
- **OTel Collector** — receives traces/metrics over OTLP (:4317/:4318).
- **Fluent Bit** — DaemonSet that ships all container logs to ELK.

### Health Check + Backup
- **`/health/`** endpoint — checks DB and Redis, returns JSON status.
- **k8s probes** — readiness and liveness probes hit `/health/` on every pod.
- **Automated backups** — daily pg_dump at 2:00 AM, 7-day retention, gzipped.
- **Disaster recovery** — restore script with a confirmation prompt.

---

## Prerequisites

- [Terraform](https://www.terraform.io/) >= 1.5
- [Ansible](https://www.ansible.com/) >= 2.14 + the `hetzner.hcloud` collection
- `kubectl`, `ssh`, `scp`, `envsubst` available in PATH
- Hetzner Cloud account with an API token (Read & Write)
- A domain with DNS pointed at Hetzner (for TLS via Let's Encrypt)

```bash
# Install the Ansible Hetzner collection (once)
ansible-galaxy collection install hetzner.hcloud
```

`./setup.sh` installs every CLI tool above on macOS (brew) or Debian/Ubuntu (apt).

---

## Quick start

### 1. Configure

```bash
cp .env.example .env   # fill in all values
```

### 2. Launch infrastructure

```bash
make keys          # generate an SSH key pair in .ssh/
make infra-up      # create 5 VMs on Hetzner (~2 min)
```

### 3. Point your domain at the master IP

```bash
cd infrastructure/tf_clean && terraform output master_public_ip
```

Create A-records at your DNS provider:

```
@          A    <master_public_ip>     # yourdomain.com
grafana    A    <master_public_ip>     # grafana.yourdomain.com
```

**Important:** DNS must resolve **before** `make configure`, otherwise cert-manager
cannot issue TLS certificates from Let's Encrypt.

### 4. Provision and deploy

```bash
make configure       # install k3s, PostgreSQL, ELK, monitoring via Ansible (~15 min)
make get-kubeconfig  # download kubeconfig from the master
make full-deploy     # build image → push to ghcr.io → deploy to k3s
```

---

## Environment variables

Copy `.env.example` to `.env` and fill in all values. The file is gitignored.

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

## Make targets

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
  make db-backup        run on-demand backup on the postgres VM
  make db-backup-list   list available backups
  make db-restore BACKUP=<path>  restore from a backup file

Full pipelines:
  make all              keys → infra-up → configure
  make full-deploy      build-push → create-secrets → deploy
  make fclean           destroy VMs + remove .ssh/ and .kube/
```

---

## Data flow

```
Logs:    k8s containers → Fluent Bit → Logstash (10.0.1.30:5000) → Elasticsearch → Kibana
Metrics: k3s nodes      → node-exporter → Prometheus → Grafana
         PostgreSQL VM  → postgres_exporter (10.0.1.20:9187) → Prometheus → Grafana
         app            → OTel SDK → OTel Collector → Prometheus (metrics) / Tempo (traces)
```

## Backup & disaster recovery

Daily pg_dump runs at 2:00 AM on the postgres VM; backups are stored at
`/var/backups/postgresql/` as `*.sql.gz` with 7-day retention.

```bash
make db-backup-list                                   # list backups
make db-backup                                        # run one now
make db-restore BACKUP=/var/backups/postgresql/<file> # restore (prompts to confirm)
```
