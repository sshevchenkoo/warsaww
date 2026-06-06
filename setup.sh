#!/usr/bin/env bash
# Bootstrap: ставит все CLI-инструменты для работы с этим проектом.
# Поддерживает macOS (через brew) и Debian/Ubuntu (через apt).
#
# Usage:  ./setup.sh
#
# Ставит: terraform, ansible, kubectl, helm, docker (info), envsubst,
#         python hcloud lib, ansible-galaxy: hetzner.hcloud

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { printf "${GREEN}==>${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}WARN:${NC} %s\n" "$*"; }
err()  { printf "${RED}ERROR:${NC} %s\n" "$*" >&2; }

# ─── Детект OS ────────────────────────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
    Darwin) PKG="brew" ;;
    Linux)
        if command -v apt-get >/dev/null 2>&1; then
            PKG="apt"
        else
            err "Linux обнаружен, но apt-get отсутствует. Поддерживаем только Debian/Ubuntu."
            exit 1
        fi
        ;;
    *) err "Неподдерживаемая ОС: $OS"; exit 1 ;;
esac

log "Обнаружена $OS, использую $PKG"

# ─── macOS via Homebrew ───────────────────────────────────────────────────────
if [[ "$PKG" == "brew" ]]; then
    if ! command -v brew >/dev/null 2>&1; then
        log "Homebrew не найден — устанавливаю..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi

    log "Ставлю CLI-инструменты через brew..."
    brew install \
        terraform \
        ansible \
        kubernetes-cli \
        helm \
        gettext \
        python3

    # envsubst на macOS требует --force-link gettext
    brew link --force gettext >/dev/null 2>&1 || true

    if ! command -v docker >/dev/null 2>&1; then
        warn "Docker не найден. Поставь Docker Desktop вручную:"
        warn "  brew install --cask docker"
        warn "Или с сайта: https://www.docker.com/products/docker-desktop"
    fi
fi

# ─── Ubuntu/Debian via apt ────────────────────────────────────────────────────
if [[ "$PKG" == "apt" ]]; then
    log "Обновляю apt-кэш и ставлю базовые пакеты..."
    sudo apt-get update
    sudo apt-get install -y \
        curl \
        gnupg \
        lsb-release \
        gettext \
        python3-pip \
        software-properties-common

    # Terraform — HashiCorp apt-репо
    if ! command -v terraform >/dev/null 2>&1; then
        log "Ставлю Terraform из HashiCorp репозитория..."
        curl -fsSL https://apt.releases.hashicorp.com/gpg \
            | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
        echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
            | sudo tee /etc/apt/sources.list.d/hashicorp.list >/dev/null
        sudo apt-get update
        sudo apt-get install -y terraform
    fi

    # kubectl — Kubernetes apt-репо (stable v1.29)
    if ! command -v kubectl >/dev/null 2>&1; then
        log "Ставлю kubectl..."
        sudo mkdir -p /etc/apt/keyrings
        curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key \
            | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-archive-keyring.gpg
        echo "deb [signed-by=/etc/apt/keyrings/kubernetes-archive-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /" \
            | sudo tee /etc/apt/sources.list.d/kubernetes.list >/dev/null
        sudo apt-get update
        sudo apt-get install -y kubectl
    fi

    # Helm — официальный установочный скрипт
    if ! command -v helm >/dev/null 2>&1; then
        log "Ставлю Helm..."
        curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    fi

    # Ansible через pip — версия свежее apt
    if ! command -v ansible >/dev/null 2>&1; then
        log "Ставлю Ansible через pip..."
        pip3 install --user ansible
        warn "Если ansible не находится — добавь ~/.local/bin в PATH:"
        warn "  echo 'export PATH=\$HOME/.local/bin:\$PATH' >> ~/.bashrc"
    fi

    if ! command -v docker >/dev/null 2>&1; then
        warn "Docker не найден. Установи Docker Engine отдельно:"
        warn "  https://docs.docker.com/engine/install/ubuntu/"
    fi
fi

# ─── Общее: Python-зависимости для hcloud inventory plugin ────────────────────
log "Ставлю Python-библиотеки для Ansible hcloud inventory..."
pip3 install --user --upgrade hcloud requests 2>/dev/null || \
    pip3 install --user --break-system-packages --upgrade hcloud requests

# ─── Общее: Ansible Galaxy collections ────────────────────────────────────────
log "Ставлю Ansible Galaxy collection hetzner.hcloud..."
ansible-galaxy collection install hetzner.hcloud

# ─── Проверка ─────────────────────────────────────────────────────────────────
echo ""
log "Проверка установленных тулов:"
MISSING=0
for tool in terraform ansible kubectl helm envsubst docker; do
    if command -v "$tool" >/dev/null 2>&1; then
        VERSION=$("$tool" --version 2>&1 | head -1 | tr -d '\n')
        printf "  ${GREEN}✓${NC} %-12s %s\n" "$tool" "$VERSION"
    else
        printf "  ${RED}✗${NC} %-12s НЕ НАЙДЕН\n" "$tool"
        MISSING=1
    fi
done

echo ""
if [[ $MISSING -eq 0 ]]; then
    log "Всё на месте!"
else
    warn "Часть тулов отсутствует — см. сообщения выше."
fi

echo ""
log "Следующий шаг:"
echo "  cp .env.example .env       # заполнить токены и пароли"
echo "  make all                   # keys → infra-up → configure"
echo "  make full-deploy           # build-push → secrets → deploy"
