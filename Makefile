.PHONY: help keys check-keys \
        dev app-up app-down app-logs app-seed web web-bg web-logs \
        do-infra-up do-infra-plan do-infra-down do-kubeconfig do-db-init \
        do-images do-platform do-deploy do-elk

# ─── Load .env ────────────────────────────────────────────────────────────────
-include .env
export

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR    := $(shell pwd)
SSH_DIR     := $(ROOT_DIR)/.ssh
# Override SSH_KEY in .env to reuse an existing private key (e.g. ~/.ssh/hetzner_warsaw).
SSH_KEY     ?= $(SSH_DIR)/id_ed25519
SSH_KEY_PUB := $(SSH_KEY).pub
ANSIBLE_DIR := $(ROOT_DIR)/infrastructure/ansible
BACKEND_DIR  := $(ROOT_DIR)/backend
FRONTEND_DIR := $(ROOT_DIR)/frontend
WEB_LOG      := /tmp/warsaw-web-dev.log

# ─── DigitalOcean prod (DOKS) ─────────────────────────────────────────────────
DO_TF_DIR    := $(ROOT_DIR)/infrastructure/digitalocean
KUBECONFIG_DO := $(ROOT_DIR)/.kube/config-do
WARSAW_API_IMAGE := ghcr.io/$(GITHUB_USER)/warsaw-events
WARSAW_WEB_IMAGE := ghcr.io/$(GITHUB_USER)/warsaw-web

# ─── Image tag (used by the do-* image build/deploy) ──────────────────────────
# Default to the short git SHA so images are immutable and traceable to a commit.
# This is what makes `do-deploy` self-roll: the tag in the rendered manifest
# changes per commit, so `kubectl apply` sees a new pod spec and rolls out — no
# manual `kubectl rollout restart` (which `:latest` needed, since an unchanged
# manifest is a no-op). Override for one-offs: `IMAGE_TAG=latest make do-deploy`.
IMAGE_TAG ?= $(shell git rev-parse --short HEAD)

# ─── Colors ───────────────────────────────────────────────────────────────────
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
NC     := \033[0m

# ─── Help ─────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  $(GREEN)Warsaw events — local dev + DigitalOcean prod$(NC)"
	@echo ""
	@echo "  $(YELLOW)Local app (docker-compose):$(NC)"
	@echo "    make dev             — start everything (API :8000 + web :3000) in the background"
	@echo "    make app-down        — stop everything (frontend + backend stack)"
	@echo "    make app-up          — build + start API, Postgres, Redis on :8000"
	@echo "    make app-seed        — load Warsaw places + events into the DB"
	@echo "    make web             — start the Next.js frontend on :3000 (foreground)"
	@echo "    make app-logs        — follow the API logs"
	@echo "    make web-logs        — follow the frontend logs"
	@echo ""
	@echo "  $(YELLOW)DigitalOcean prod (DOKS) — full runbook: docs/hosting-digitalocean.md:$(NC)"
	@echo "    make keys            — generate the SSH key in .ssh/ (used by do-elk)"
	@echo "    make do-infra-up     — Terraform: VPC + DOKS + managed Postgres + ELK droplet"
	@echo "    make do-db-init      — enable pgvector on the managed DB (once)"
	@echo "    make do-images       — build + push warsaw-events / warsaw-web to ghcr.io"
	@echo "    make do-platform     — Helm: ingress-nginx, cert-manager, monitoring, fluent-bit"
	@echo "    make do-deploy       — apply the warsaw app manifests"
	@echo "    make do-elk          — provision the ELK droplet (Ansible)"
	@echo "    make do-infra-down   — destroy the whole DO prod env (stop the bill)"
	@echo ""

# ─── SSH key (used by do-elk to reach the ELK droplet) ────────────────────────
keys:
	@if [ -f "$(SSH_KEY)" ]; then \
		echo "$(YELLOW)SSH key already exists: $(SSH_KEY)$(NC)"; \
	else \
		mkdir -p $(SSH_DIR); \
		ssh-keygen -t ed25519 -C "warsaw-deploy" -f $(SSH_KEY) -N ""; \
		chmod 700 $(SSH_DIR); \
		chmod 600 $(SSH_KEY); \
		chmod 644 $(SSH_KEY_PUB); \
		echo "$(GREEN)SSH key created in $(SSH_DIR)$(NC)"; \
	fi

check-keys:
	@if [ ! -f "$(SSH_KEY)" ]; then \
		echo "$(RED)SSH key not found. Run: make keys$(NC)"; \
		exit 1; \
	fi

# ─── Local app (Warsaw events) ────────────────────────────────────────────────
# Runs the app stack from backend/docker-compose.yml (API + Postgres + Redis)
# and the Next.js frontend. Needs backend/.env (API keys) — see backend/README.

# One command for local testing: backend stack + frontend, both in the
# background, so the command returns immediately and `make app-down` stops it
# all. Data persists in the pgdata volume, so seeding is a one-time
# `make app-seed` (not needed on every run).
dev: app-up web-bg
	@echo "$(GREEN)Up:$(NC) API http://localhost:8000  ·  web http://localhost:3000"
	@echo "  logs: $(YELLOW)make app-logs$(NC) (api) / $(YELLOW)make web-logs$(NC) (web)    stop: $(YELLOW)make app-down$(NC)"

app-up:
	@echo "$(GREEN)Starting the local app stack (API + Postgres + Redis)...$(NC)"
	cd $(BACKEND_DIR) && docker compose up -d --build
	@echo "$(GREEN)API up: http://localhost:8000  (health: /health)$(NC)"
	@echo "Next: $(YELLOW)make app-seed$(NC) to load data, then $(YELLOW)make web$(NC) for the UI"

app-seed:
	@echo "$(GREEN)Loading places (OSM + Wikidata)...$(NC)"
	cd $(BACKEND_DIR) && docker compose exec api python -m app.ingestion.runner --source=places
	@echo "$(GREEN)Loading Facebook events (Apify)...$(NC)"
	cd $(BACKEND_DIR) && docker compose exec api python -m app.ingestion.runner --source=facebook_events

web:
	cd $(FRONTEND_DIR) && { [ -d node_modules ] || npm install; } && npm run dev

# Frontend in the background (used by `make dev`); logs go to WEB_LOG.
web-bg:
	@cd $(FRONTEND_DIR) && { [ -d node_modules ] || npm install; }
	@echo "$(GREEN)Starting the frontend on :3000 (background, logs: make web-logs)...$(NC)"
	@nohup sh -c 'cd $(FRONTEND_DIR) && npm run dev' > $(WEB_LOG) 2>&1 < /dev/null &

web-logs:
	@tail -F $(WEB_LOG)

app-logs:
	cd $(BACKEND_DIR) && docker compose logs -f api

# Stops everything: the background frontend (whatever holds :3000) and the
# backend stack. Data is kept in the pgdata volume.
app-down:
	@PIDS=$$(lsof -ti:3000 2>/dev/null); if [ -n "$$PIDS" ]; then kill $$PIDS 2>/dev/null && echo "$(GREEN)Frontend stopped$(NC)"; fi
	cd $(BACKEND_DIR) && docker compose down
	@echo "$(GREEN)App stack stopped (data kept in the pgdata volume)$(NC)"

# ─── DigitalOcean prod (DOKS) ─────────────────────────────────────────────────
# Prereqs: terraform, kubectl, helm, ansible, envsubst, psql, doctl/ssh.
# All config comes from .env (exported below): DIGITALOCEAN_TOKEN,
# TF_VAR_ssh_public_key, TF_VAR_admin_ip, GITHUB_USER/TOKEN, WARSAW_DOMAIN,
# ACME_EMAIL, GRAFANA_PASSWORD, KIBANA_PASSWORD. No terraform.tfvars needed.
# Full runbook: docs/hosting-digitalocean.md
KDO := KUBECONFIG=$(KUBECONFIG_DO)

do-infra-up:        ## Terraform: VPC + DOKS + managed Postgres + ELK droplet
	cd $(DO_TF_DIR) && terraform init -upgrade && terraform apply -auto-approve
	@$(MAKE) do-kubeconfig

do-infra-plan:
	cd $(DO_TF_DIR) && terraform init -upgrade && terraform plan

do-infra-down:      ## Destroy the whole DO prod env (stop the bill)
	cd $(DO_TF_DIR) && terraform destroy -auto-approve

do-kubeconfig:      ## Save the DOKS kubeconfig to .kube/config-do
	@mkdir -p $(ROOT_DIR)/.kube
	cd $(DO_TF_DIR) && terraform output -raw kubeconfig > $(KUBECONFIG_DO)
	@chmod 600 $(KUBECONFIG_DO)
	@echo "$(GREEN)kubeconfig → $(KUBECONFIG_DO)$(NC)"

do-db-init:         ## Enable pgvector + pg_trgm on the managed DB (run once, needs psql)
	# Uses the PUBLIC admin URI (reachable from your admin IP) pointed at the
	# `events` DB — the private database_url only resolves inside the VPC.
	# vector → semantic search; pg_trgm → lexical leg of hybrid search.
	@URL=$$(cd $(DO_TF_DIR) && terraform output -raw database_admin_uri | sed 's#/defaultdb#/events#'); \
	 psql "$$URL" -c 'CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;' && echo "$(GREEN)pgvector + pg_trgm enabled$(NC)"

do-db-role:         ## Create/rotate the least-privilege app DB role (admin, idempotent)
	# Least-privilege DML-only role so the app no longer runs as `doadmin`
	# (audit #4). Run AFTER do-db-init and BEFORE do-db-migrate. Then set
	# DATABASE_URL in backend/k8s/secret.yml to this role and redeploy.
	@[ -n "$(WARSAW_APP_DB_PASSWORD)" ] || (echo "$(RED)WARSAW_APP_DB_PASSWORD not set in .env$(NC)" && exit 1)
	@URL=$$(cd $(DO_TF_DIR) && terraform output -raw database_admin_uri | sed 's#/defaultdb#/events#'); \
	 psql "$$URL" -v ON_ERROR_STOP=1 -v pw="$(WARSAW_APP_DB_PASSWORD)" -f $(BACKEND_DIR)/db/app-role.sql \
	 && echo "$(GREEN)warsaw_app role ready (DML-only)$(NC)"

do-db-monitor-role: ## Create/rotate the read-only monitoring DB role (admin, idempotent)
	# Read-only role (pg_monitor) for prometheus-postgres-exporter, so metrics
	# collection never runs as doadmin. Run once (re-run to rotate the password).
	# Then create the `postgres-exporter-dsn` secret in `monitoring` (see runbook).
	@[ -n "$(PG_MONITOR_PASSWORD)" ] || (echo "$(RED)PG_MONITOR_PASSWORD not set in .env$(NC)" && exit 1)
	@URL=$$(cd $(DO_TF_DIR) && terraform output -raw database_admin_uri | sed 's#/defaultdb#/events#'); \
	 psql "$$URL" -v ON_ERROR_STOP=1 -v pw="$(PG_MONITOR_PASSWORD)" -f $(BACKEND_DIR)/db/monitor-role.sql \
	 && echo "$(GREEN)warsaw_monitor role ready (read-only)$(NC)"

do-db-migrate:      ## Create/upgrade the schema as admin (run before deploy when schema changed)
	# Schema bootstrap (extensions + create_all + indexes) as `doadmin`, since
	# the runtime role is DML-only (DB_BOOTSTRAP=false in the manifests). Uses the
	# deployed image so the models match exactly. Needs do-images to have run.
	# Point at the `events` DB and force the psycopg (v3) driver — the raw admin
	# URI is `postgresql://`, which SQLAlchemy maps to psycopg2 (not in the image).
	@URL=$$(cd $(DO_TF_DIR) && terraform output -raw database_admin_uri \
	    | sed -E 's#/defaultdb#/events#; s#^postgresql(\+[a-z0-9]+)?://#postgresql+psycopg://#'); \
	 docker run --rm --platform linux/amd64 -e DATABASE_URL="$$URL" \
	   $(WARSAW_API_IMAGE):$(IMAGE_TAG) python -c "from app.main import _create_schema; _create_schema()" \
	 && echo "$(GREEN)schema migrated (admin)$(NC)"

do-images:          ## Build (linux/amd64) + push warsaw-events / warsaw-web to ghcr.io
	# DOKS nodes are amd64 — build for that platform explicitly so images built on
	# an Apple-Silicon (arm64) Mac don't "exec format error" in the cluster.
	# Tag each image with the immutable SHA (what the manifests deploy) and also
	# `:latest` (convenience for ad-hoc `docker pull`); deploy strictly by SHA.
	echo "$(GITHUB_TOKEN)" | docker login ghcr.io -u $(GITHUB_USER) --password-stdin
	docker buildx build --platform linux/amd64 -t $(WARSAW_API_IMAGE):$(IMAGE_TAG) -t $(WARSAW_API_IMAGE):latest --push $(BACKEND_DIR)
	docker buildx build --platform linux/amd64 -t $(WARSAW_WEB_IMAGE):$(IMAGE_TAG) -t $(WARSAW_WEB_IMAGE):latest --push $(FRONTEND_DIR)

do-platform:        ## Helm: ingress-nginx, cert-manager(+issuer), monitoring (full parity), fluent-bit
	@[ -n "$(GRAFANA_PASSWORD)" ] || (echo "$(RED)GRAFANA_PASSWORD not set in .env$(NC)" && exit 1)
	@[ -n "$(WARSAW_DOMAIN)" ]    || (echo "$(RED)WARSAW_DOMAIN not set in .env$(NC)"    && exit 1)
	helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx >/dev/null 2>&1 || true
	helm repo add jetstack https://charts.jetstack.io >/dev/null 2>&1 || true
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
	helm repo add grafana https://grafana.github.io/helm-charts >/dev/null 2>&1 || true
	helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts >/dev/null 2>&1 || true
	helm repo add fluent https://fluent.github.io/helm-charts >/dev/null 2>&1 || true
	helm repo update >/dev/null
	$(KDO) helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace
	$(KDO) helm upgrade --install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set crds.enabled=true
	# CoreDNS rewrite so cert-manager's HTTP-01 self-check reaches the ingress
	# ClusterIP directly (DOKS+Cilium doesn't hairpin to the LB external IP).
	@envsubst < $(ROOT_DIR)/platform/coredns-custom.yaml | $(KDO) kubectl apply -f -
	$(KDO) kubectl -n kube-system rollout restart deployment coredns
	# kube-prometheus-stack WITH values (Grafana pw, retention/persistence, resources,
	# scrape configs). Release name matches the PrometheusRule `release` label so the
	# operator picks up the shared alert rules. --wait so the PrometheusRule CRD exists.
	@envsubst < $(ROOT_DIR)/platform/kube-prometheus-stack-values.yaml | \
		$(KDO) helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
		-n monitoring --create-namespace --wait -f -
	# Tracing backend + collector.
	$(KDO) helm upgrade --install tempo grafana/tempo -n monitoring -f $(ROOT_DIR)/platform/tempo-values.yaml
	$(KDO) helm upgrade --install otel-collector open-telemetry/opentelemetry-collector -n monitoring -f $(ROOT_DIR)/platform/otel-collector-values.yaml
	# postgres_exporter against the managed DB so the pg_* panels/alerts have
	# data. Needs the `warsaw_monitor` role (make do-db-monitor-role) and the
	# postgres-exporter-dsn secret in `monitoring` (see the runbook); harmless to
	# install first — it just reports pg_up=0 until the secret/role exist.
	$(KDO) helm upgrade --install prometheus-postgres-exporter prometheus-community/prometheus-postgres-exporter -n monitoring -f $(ROOT_DIR)/platform/postgres-exporter-values.yaml
	# Alert rules + custom dashboard + Tempo datasource.
	$(KDO) kubectl apply -f $(ROOT_DIR)/platform/alerting-rules.yaml
	$(KDO) kubectl apply -f $(ROOT_DIR)/platform/grafana-dashboard.yaml
	$(KDO) kubectl apply -f $(ROOT_DIR)/platform/grafana-tempo-datasource.yaml
	@ELK_PRIVATE_IP=$$(cd $(DO_TF_DIR) && terraform output -raw elk_private_ip) envsubst < $(ROOT_DIR)/platform/fluent-bit-values.yaml | \
		$(KDO) helm upgrade --install fluent-bit fluent/fluent-bit -n logging --create-namespace -f -
	@ACME_EMAIL=$(ACME_EMAIL) envsubst < $(ROOT_DIR)/platform/clusterissuer.yaml | $(KDO) kubectl apply -f -

do-deploy:          ## Apply the warsaw app manifests (managed DB, no in-cluster PG)
	$(KDO) kubectl apply -f $(BACKEND_DIR)/k8s/00-namespace.yml
	$(KDO) kubectl apply -f $(BACKEND_DIR)/k8s/secret.yml
	$(KDO) kubectl apply -f $(BACKEND_DIR)/k8s/45-networkpolicies.yml
	$(KDO) kubectl apply -f $(BACKEND_DIR)/k8s/20-redis.yml
	GITHUB_USER=$(GITHUB_USER) IMAGE_TAG=$(IMAGE_TAG) envsubst < $(BACKEND_DIR)/k8s/30-api.yml | $(KDO) kubectl apply -f -
	$(KDO) kubectl apply -f $(BACKEND_DIR)/k8s/35-pdb.yml
	GITHUB_USER=$(GITHUB_USER) IMAGE_TAG=$(IMAGE_TAG) envsubst < $(BACKEND_DIR)/k8s/50-cronjobs.yml | $(KDO) kubectl apply -f -
	GITHUB_USER=$(GITHUB_USER) IMAGE_TAG=$(IMAGE_TAG) envsubst < $(FRONTEND_DIR)/k8s/web.yml | $(KDO) kubectl apply -f -
	WARSAW_DOMAIN=$(WARSAW_DOMAIN) envsubst < $(BACKEND_DIR)/k8s/40-ingress.yml | $(KDO) kubectl apply -f -

do-elk:             ## Provision the ELK droplet with Ansible
	@PUB=$$(cd $(DO_TF_DIR) && terraform output -raw elk_public_ip); \
	 PRIV=$$(cd $(DO_TF_DIR) && terraform output -raw elk_private_ip); \
	 ELK_PUBLIC_IP=$$PUB ELK_PRIVATE_IP=$$PRIV KIBANA_PASSWORD=$(KIBANA_PASSWORD) \
	   envsubst < $(ANSIBLE_DIR)/inventory.do.yml > /tmp/inv.do.yml; \
	 cd $(ANSIBLE_DIR) && ansible-playbook -i /tmp/inv.do.yml playbooks/elk.yml --private-key $(SSH_KEY)
