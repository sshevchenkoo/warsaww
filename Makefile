.PHONY: help check-env keys check-keys \
        infra-up infra-down infra-plan \
        configure ping \
        build push build-push \
        get-kubeconfig create-secrets deploy full-deploy \
        db-backup db-restore db-backup-list \
        all fclean \
        app-up app-down app-logs app-seed web

# ─── Load .env ────────────────────────────────────────────────────────────────
-include .env
export

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR    := $(shell pwd)
SSH_DIR     := $(ROOT_DIR)/.ssh
SSH_KEY     := $(SSH_DIR)/id_ed25519
SSH_KEY_PUB := $(SSH_DIR)/id_ed25519.pub
TF_DIR      := $(ROOT_DIR)/infrastructure/tf_clean
ANSIBLE_DIR := $(ROOT_DIR)/infrastructure/ansible
K8S_DIR     := $(ROOT_DIR)/k8s
KUBECONFIG  := $(ROOT_DIR)/.kube/config
BACKEND_DIR  := $(ROOT_DIR)/backend
FRONTEND_DIR := $(ROOT_DIR)/frontend

# ─── Terraform env vars (read automatically from .env via export) ──────────────
export TF_VAR_hcloud_token=$(HCLOUD_TOKEN)
export TF_VAR_your_ssh_ip=$(YOUR_SSH_IP)

# ─── Image ────────────────────────────────────────────────────────────────────
IMAGE     := ghcr.io/$(GITHUB_USER)/transcendence
IMAGE_TAG ?= latest

# ─── Colors ───────────────────────────────────────────────────────────────────
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
NC     := \033[0m

# ─── Help ─────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  $(GREEN)Transcendence — infrastructure management$(NC)"
	@echo ""
	@echo "  $(YELLOW)First time setup:$(NC)"
	@echo "    cp .env.example .env  — fill in your values (once)"
	@echo ""
	@echo "  $(YELLOW)Local app (Warsaw events):$(NC)"
	@echo "    make app-up          — build + start API, Postgres, Redis on :8000"
	@echo "    make app-seed        — load Warsaw places + events into the DB"
	@echo "    make web             — start the Next.js frontend on :3000"
	@echo "    make app-logs        — follow the API logs"
	@echo "    make app-down        — stop the local app stack"
	@echo ""
	@echo "  $(YELLOW)Infrastructure:$(NC)"
	@echo "    make keys            — generate SSH keys in .ssh/"
	@echo "    make infra-up        — create VMs on Hetzner"
	@echo "    make infra-plan      — show plan without applying"
	@echo "    make infra-down      — destroy VMs on Hetzner"
	@echo "    make configure       — provision servers with Ansible"
	@echo "    make ping            — check Ansible can reach all hosts"
	@echo ""
	@echo "  $(YELLOW)Docker image:$(NC)"
	@echo "    make build           — build production image"
	@echo "    make push            — push image to ghcr.io"
	@echo "    make build-push      — build + push"
	@echo ""
	@echo "  $(YELLOW)Kubernetes:$(NC)"
	@echo "    make get-kubeconfig  — download kubeconfig from master"
	@echo "    make create-secrets  — create k8s Secret from .env"
	@echo "    make deploy          — apply k8s manifests"
	@echo ""
	@echo "  $(YELLOW)Monitoring (deployed by 'make configure'):$(NC)"
	@echo "    Prometheus + Grafana  — https://grafana.DOMAIN (grafana_password from .env)"
	@echo "    Tempo                 — traces backend (ClusterIP, via Grafana)"
	@echo "    OTel Collector        — OTLP :4317/:4318 (ClusterIP inside k8s)"
	@echo "    Fluent Bit            — ships k8s logs → ELK VM :5000"
	@echo "    Kibana                — http://ELK_IP:5601 (firewall: your IP only)"
	@echo ""
	@echo "  $(YELLOW)Database backup & restore:$(NC)"
	@echo "    make db-backup       — run on-demand backup on postgres VM"
	@echo "    make db-backup-list  — list available backups"
	@echo "    make db-restore BACKUP=<path> — restore from backup file"
	@echo ""
	@echo "  $(YELLOW)Full pipelines:$(NC)"
	@echo "    make all             — keys → infra-up → configure"
	@echo "    make full-deploy     — build-push → create-secrets → deploy"
	@echo "    make fclean          — destroy everything + remove .ssh/"
	@echo ""

# ─── Env check ────────────────────────────────────────────────────────────────
check-env:
	@if [ ! -f "$(ROOT_DIR)/.env" ]; then \
		echo "$(RED).env not found!$(NC)"; \
		echo "  cp .env.example .env"; \
		exit 1; \
	fi
	@[ -n "$(HCLOUD_TOKEN)" ]      || (echo "$(RED)HCLOUD_TOKEN not set in .env$(NC)"      && exit 1)
	@[ -n "$(YOUR_SSH_IP)" ]       || (echo "$(RED)YOUR_SSH_IP not set in .env$(NC)"       && exit 1)
	@[ -n "$(GITHUB_USER)" ]       || (echo "$(RED)GITHUB_USER not set in .env$(NC)"       && exit 1)
	@[ -n "$(GITHUB_TOKEN)" ]      || (echo "$(RED)GITHUB_TOKEN not set in .env$(NC)"      && exit 1)
	@[ -n "$(DOMAIN)" ]            || (echo "$(RED)DOMAIN not set in .env$(NC)"            && exit 1)
	@[ -n "$(LETSENCRYPT_EMAIL)" ] || (echo "$(RED)LETSENCRYPT_EMAIL not set in .env$(NC)" && exit 1)
	@[ -n "$(POSTGRES_PASSWORD)" ] || (echo "$(RED)POSTGRES_PASSWORD not set in .env$(NC)" && exit 1)
	@[ -n "$(DJANGO_SECRET_KEY)" ] || (echo "$(RED)DJANGO_SECRET_KEY not set in .env$(NC)" && exit 1)
	@[ -n "$(GRAFANA_PASSWORD)" ]  || (echo "$(RED)GRAFANA_PASSWORD not set in .env$(NC)"  && exit 1)
	@[ -n "$(KIBANA_PASSWORD)" ]   || (echo "$(RED)KIBANA_PASSWORD not set in .env$(NC)"   && exit 1)
	@echo "$(GREEN).env OK$(NC)"

# ─── SSH keys ─────────────────────────────────────────────────────────────────
keys:
	@if [ -f "$(SSH_KEY)" ]; then \
		echo "$(YELLOW)SSH key already exists: $(SSH_KEY)$(NC)"; \
	else \
		mkdir -p $(SSH_DIR); \
		ssh-keygen -t ed25519 -C "transcendence-deploy" -f $(SSH_KEY) -N ""; \
		chmod 700 $(SSH_DIR); \
		chmod 600 $(SSH_KEY); \
		chmod 644 $(SSH_KEY_PUB); \
		echo "$(GREEN)SSH keys created in $(SSH_DIR)$(NC)"; \
	fi

check-keys:
	@if [ ! -f "$(SSH_KEY)" ]; then \
		echo "$(RED)SSH key not found. Run: make keys$(NC)"; \
		exit 1; \
	fi

# ─── Terraform ────────────────────────────────────────────────────────────────
infra-up: check-env check-keys
	@echo "$(GREEN)Creating infrastructure on Hetzner...$(NC)"
	cd $(TF_DIR) && terraform init -upgrade
	cd $(TF_DIR) && terraform apply \
		-var="ssh_public_key=$$(cat $(SSH_KEY_PUB))" \
		-auto-approve
	@echo "$(GREEN)Done! IPs:$(NC)"
	cd $(TF_DIR) && terraform output

infra-plan: check-env check-keys
	cd $(TF_DIR) && terraform init -upgrade
	cd $(TF_DIR) && terraform plan \
		-var="ssh_public_key=$$(cat $(SSH_KEY_PUB))"

infra-down: check-env check-keys
	@echo "$(RED)Destroying infrastructure on Hetzner...$(NC)"
	cd $(TF_DIR) && terraform destroy \
		-var="ssh_public_key=$$(cat $(SSH_KEY_PUB))" \
		-auto-approve
	@echo "$(GREEN)Infrastructure destroyed$(NC)"

# ─── Ansible ──────────────────────────────────────────────────────────────────
configure: check-env check-keys
	@echo "$(YELLOW)Waiting for VMs to accept SSH...$(NC)"
	cd $(ANSIBLE_DIR) && \
		HCLOUD_TOKEN="$(HCLOUD_TOKEN)" \
		ANSIBLE_PRIVATE_KEY_FILE=$(SSH_KEY) \
		ansible all -m wait_for_connection -a "timeout=180 delay=5"
	@echo "$(GREEN)Provisioning servers with Ansible...$(NC)"
	cd $(ANSIBLE_DIR) && \
		HCLOUD_TOKEN="$(HCLOUD_TOKEN)" \
		ANSIBLE_PRIVATE_KEY_FILE=$(SSH_KEY) \
		ansible-playbook site.yml \
		--extra-vars "postgres_password=$(POSTGRES_PASSWORD) \
		              django_secret_key=$(DJANGO_SECRET_KEY) \
		              domain=$(DOMAIN) \
		              letsencrypt_email=$(LETSENCRYPT_EMAIL) \
		              grafana_password=$(GRAFANA_PASSWORD) \
		              kibana_password=$(KIBANA_PASSWORD) \
		              alertmanager_telegram_token=$(ALERTMANAGER_TELEGRAM_TOKEN) \
		              alertmanager_telegram_chat_id=$(ALERTMANAGER_TELEGRAM_CHAT_ID)"
	@echo "$(GREEN)Servers provisioned!$(NC)"

ping: check-env check-keys
	cd $(ANSIBLE_DIR) && \
		HCLOUD_TOKEN="$(HCLOUD_TOKEN)" \
		ANSIBLE_PRIVATE_KEY_FILE=$(SSH_KEY) \
		ansible all -m ping

# ─── Docker image ─────────────────────────────────────────────────────────────
build: check-env
	@echo "$(GREEN)Building $(IMAGE):$(IMAGE_TAG)...$(NC)"
	docker build \
		--target production \
		-t $(IMAGE):$(IMAGE_TAG) \
		docker_compose/backend/
	@echo "$(GREEN)Image built$(NC)"

push: check-env
	echo "$(GITHUB_TOKEN)" | docker login ghcr.io -u $(GITHUB_USER) --password-stdin
	docker push $(IMAGE):$(IMAGE_TAG)
	@echo "$(GREEN)Image pushed: $(IMAGE):$(IMAGE_TAG)$(NC)"

build-push: build push

# ─── Kubernetes ───────────────────────────────────────────────────────────────
get-kubeconfig: check-env check-keys
	@MASTER_IP=$$(cd $(TF_DIR) && terraform output -raw master_public_ip); \
	echo "$(GREEN)Downloading kubeconfig from $$MASTER_IP...$(NC)"; \
	mkdir -p $(ROOT_DIR)/.kube; \
	scp -i $(SSH_KEY) -o StrictHostKeyChecking=no \
		root@$$MASTER_IP:/etc/rancher/k3s/k3s.yaml $(KUBECONFIG); \
	sed -i.bak "s|https://127.0.0.1:6443|https://$$MASTER_IP:6443|g" $(KUBECONFIG) && rm -f $(KUBECONFIG).bak; \
	chmod 600 $(KUBECONFIG); \
	echo "$(GREEN)Kubeconfig saved to .kube/config$(NC)"

create-secrets: check-env
	KUBECONFIG=$(KUBECONFIG) kubectl apply -f $(K8S_DIR)/namespace.yml
	KUBECONFIG=$(KUBECONFIG) kubectl create secret generic app-secrets \
		--namespace transcendence \
		--from-literal=DATABASE_URL="postgresql://transcendence:$(POSTGRES_PASSWORD)@10.0.1.20:5432/transcendence" \
		--from-literal=SECRET_KEY="$(DJANGO_SECRET_KEY)" \
		--from-literal=ALLOWED_HOSTS="$(DOMAIN)" \
		--dry-run=client -o yaml | KUBECONFIG=$(KUBECONFIG) kubectl apply -f -
	@echo "$(GREEN)Secrets created!$(NC)"
	@if KUBECONFIG=$(KUBECONFIG) kubectl get deploy/backend -n transcendence >/dev/null 2>&1; then \
		echo "$(YELLOW)Restarting backend to pick up new secrets...$(NC)"; \
		KUBECONFIG=$(KUBECONFIG) kubectl rollout restart deploy/backend -n transcendence; \
	fi

deploy: check-env
	@if [ ! -f "$(KUBECONFIG)" ]; then \
		echo "$(RED)Kubeconfig not found. Run: make get-kubeconfig$(NC)"; \
		exit 1; \
	fi
	KUBECONFIG=$(KUBECONFIG) kubectl apply -f $(K8S_DIR)/namespace.yml
	KUBECONFIG=$(KUBECONFIG) kubectl apply -f $(K8S_DIR)/redis/
	GITHUB_USER=$(GITHUB_USER) IMAGE_TAG=$(IMAGE_TAG) \
		envsubst < $(K8S_DIR)/backend/deployment.yml | \
		KUBECONFIG=$(KUBECONFIG) kubectl apply -f -
	KUBECONFIG=$(KUBECONFIG) kubectl apply -f $(K8S_DIR)/backend/service.yml
	DOMAIN=$(DOMAIN) envsubst < $(K8S_DIR)/ingress.yml | \
		KUBECONFIG=$(KUBECONFIG) kubectl apply -f -
	@echo "$(GREEN)Deployed! Site: https://$(DOMAIN)$(NC)"

# ─── Full pipelines ───────────────────────────────────────────────────────────
all: keys infra-up configure
	@echo ""
	@echo "$(GREEN)Infrastructure ready!$(NC)"
	@echo "$(YELLOW)Next: make full-deploy$(NC)"

full-deploy: build-push create-secrets deploy
	@echo ""
	@echo "$(GREEN)Full deploy complete!$(NC)"
	@echo "$(YELLOW)Site: https://$(DOMAIN)$(NC)"

# ─── Database backup / restore ────────────────────────────────────────────────
POSTGRES_IP := $(shell cd $(TF_DIR) && terraform output -raw postgres_public_ip 2>/dev/null)

db-backup: check-env check-keys
	@echo "$(GREEN)Running on-demand backup on postgres VM...$(NC)"
	ssh -i $(SSH_KEY) -o StrictHostKeyChecking=no root@$(POSTGRES_IP) \
		"sudo -u postgres /usr/local/bin/pg-backup.sh"
	@echo "$(GREEN)Backup complete. Files on postgres VM: /var/backups/postgresql/$(NC)"

# Usage: make db-restore BACKUP=/var/backups/postgresql/transcendence_20240101_020000.sql.gz
db-restore: check-env check-keys
	@if [ -z "$(BACKUP)" ]; then \
		echo "$(RED)Usage: make db-restore BACKUP=<path_on_postgres_vm>$(NC)"; \
		echo "  List backups: make db-backup-list"; \
		exit 1; \
	fi
	@echo "$(RED)Restoring database from $(BACKUP)...$(NC)"
	ssh -i $(SSH_KEY) -o StrictHostKeyChecking=no root@$(POSTGRES_IP) \
		"sudo -u postgres /usr/local/bin/pg-restore.sh $(BACKUP)"

db-backup-list: check-env check-keys
	@echo "$(YELLOW)Backups on postgres VM:$(NC)"
	ssh -i $(SSH_KEY) -o StrictHostKeyChecking=no root@$(POSTGRES_IP) \
		"ls -lh /var/backups/postgresql/ 2>/dev/null || echo 'No backups yet'"

# ─── Cleanup ──────────────────────────────────────────────────────────────────
fclean: infra-down
	@echo "$(RED)Removing SSH keys and kubeconfig...$(NC)"
	rm -rf $(SSH_DIR) $(ROOT_DIR)/.kube
	@echo "$(GREEN)All cleaned up$(NC)"

# ─── Local app (Warsaw events) ────────────────────────────────────────────────
# Runs the app stack from backend/docker-compose.yml (API + Postgres + Redis)
# and the Next.js frontend. Needs backend/.env (API keys) — see backend/README.

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

app-logs:
	cd $(BACKEND_DIR) && docker compose logs -f api

app-down:
	cd $(BACKEND_DIR) && docker compose down
	@echo "$(GREEN)App stack stopped (data kept in the pgdata volume)$(NC)"
