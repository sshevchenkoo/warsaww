#!/usr/bin/env bash
# Bootstrap: installs every CLI tool needed to work with this project.
# Supports macOS (via brew) and Debian/Ubuntu (via apt).
#
# Usage:  ./setup.sh
#
# Installs: terraform, ansible, kubectl, helm, docker (info), envsubst,
#           python hcloud lib, ansible-galaxy: hetzner.hcloud

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { printf "${GREEN}==>${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}WARN:${NC} %s\n" "$*"; }
err()  { printf "${RED}ERROR:${NC} %s\n" "$*" >&2; }

# ─── OS detection ─────────────────────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
    Darwin) PKG="brew" ;;
    Linux)
        if command -v apt-get >/dev/null 2>&1; then
            PKG="apt"
        else
            err "Linux detected, but apt-get is missing. Only Debian/Ubuntu is supported."
            exit 1
        fi
        ;;
    *) err "Unsupported OS: $OS"; exit 1 ;;
esac

log "Detected $OS, using $PKG"

# ─── macOS via Homebrew ───────────────────────────────────────────────────────
if [[ "$PKG" == "brew" ]]; then
    if ! command -v brew >/dev/null 2>&1; then
        log "Homebrew not found — installing..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi

    log "Installing CLI tools via brew..."
    brew install \
        terraform \
        ansible \
        kubernetes-cli \
        helm \
        gettext \
        python3

    # envsubst on macOS requires --force-link gettext
    brew link --force gettext >/dev/null 2>&1 || true

    if ! command -v docker >/dev/null 2>&1; then
        warn "Docker not found. Install Docker Desktop manually:"
        warn "  brew install --cask docker"
        warn "Or from the website: https://www.docker.com/products/docker-desktop"
    fi
fi

# ─── Ubuntu/Debian via apt ────────────────────────────────────────────────────
if [[ "$PKG" == "apt" ]]; then
    log "Updating the apt cache and installing base packages..."
    sudo apt-get update
    sudo apt-get install -y \
        curl \
        gnupg \
        lsb-release \
        gettext \
        python3-pip \
        software-properties-common

    # Terraform — HashiCorp apt repo
    if ! command -v terraform >/dev/null 2>&1; then
        log "Installing Terraform from the HashiCorp repository..."
        curl -fsSL https://apt.releases.hashicorp.com/gpg \
            | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
        echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
            | sudo tee /etc/apt/sources.list.d/hashicorp.list >/dev/null
        sudo apt-get update
        sudo apt-get install -y terraform
    fi

    # kubectl — Kubernetes apt repo (stable v1.29)
    if ! command -v kubectl >/dev/null 2>&1; then
        log "Installing kubectl..."
        sudo mkdir -p /etc/apt/keyrings
        curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key \
            | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-archive-keyring.gpg
        echo "deb [signed-by=/etc/apt/keyrings/kubernetes-archive-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /" \
            | sudo tee /etc/apt/sources.list.d/kubernetes.list >/dev/null
        sudo apt-get update
        sudo apt-get install -y kubectl
    fi

    # Helm — official install script
    if ! command -v helm >/dev/null 2>&1; then
        log "Installing Helm..."
        curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    fi

    # Ansible via pip — newer than the apt version
    if ! command -v ansible >/dev/null 2>&1; then
        log "Installing Ansible via pip..."
        pip3 install --user ansible
        warn "If ansible is not found — add ~/.local/bin to your PATH:"
        warn "  echo 'export PATH=\$HOME/.local/bin:\$PATH' >> ~/.bashrc"
    fi

    if ! command -v docker >/dev/null 2>&1; then
        warn "Docker not found. Install Docker Engine separately:"
        warn "  https://docs.docker.com/engine/install/ubuntu/"
    fi
fi

# ─── Shared: Python deps for the hcloud inventory plugin ──────────────────────
log "Installing Python libraries for the Ansible hcloud inventory..."
pip3 install --user --upgrade hcloud requests 2>/dev/null || \
    pip3 install --user --break-system-packages --upgrade hcloud requests

# ─── Shared: Ansible Galaxy collections ───────────────────────────────────────
log "Installing the Ansible Galaxy collection hetzner.hcloud..."
ansible-galaxy collection install hetzner.hcloud

# ─── Verification ─────────────────────────────────────────────────────────────
echo ""
log "Checking installed tools:"
MISSING=0
for tool in terraform ansible kubectl helm envsubst docker; do
    if command -v "$tool" >/dev/null 2>&1; then
        VERSION=$("$tool" --version 2>&1 | head -1 | tr -d '\n')
        printf "  ${GREEN}✓${NC} %-12s %s\n" "$tool" "$VERSION"
    else
        printf "  ${RED}✗${NC} %-12s NOT FOUND\n" "$tool"
        MISSING=1
    fi
done

echo ""
if [[ $MISSING -eq 0 ]]; then
    log "Everything is in place!"
else
    warn "Some tools are missing — see the messages above."
fi

echo ""
log "Next step:"
echo "  cp .env.example .env       # fill in tokens and passwords"
echo "  make dev                   # run the app locally (API :8000 + web :3000)"
echo "  # DigitalOcean prod: make do-infra-up → do-platform → do-deploy (docs/hosting-digitalocean.md)"
