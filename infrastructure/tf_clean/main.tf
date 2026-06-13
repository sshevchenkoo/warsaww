terraform {
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
  }
  required_version = ">= 1.5"
}

provider "hcloud" {
  token = var.hcloud_token
}

# ─── SSH key ──────────────────────────────────────────────────────────────────
# A single key — stored in .ssh/id_ed25519 (generated via: make keys)
# The public key is passed from the Makefile: -var="ssh_public_key=$(cat .ssh/id_ed25519.pub)"
resource "hcloud_ssh_key" "main" {
  name       = "${var.project_name}-key"
  public_key = var.ssh_public_key
}

# ─── Network ──────────────────────────────────────────────────────────────────
module "network" {
  source = "./modules/network"

  network_name = var.project_name
  network_cidr = var.network_cidr
  subnet_cidr  = var.subnet_cidr
  network_zone = var.network_zone
}

# ─── Firewalls ────────────────────────────────────────────────────────────────
module "firewall" {
  source = "./modules/firewall"

  project_name = var.project_name
  your_ssh_ip  = var.your_ssh_ip
}

# ─── k3s Master ───────────────────────────────────────────────────────────────
module "k3s_master" {
  source = "./modules/vm"

  name         = "${var.project_name}-master"
  server_type  = var.k3s_server_type
  location     = var.location
  image        = var.os_image
  ssh_key_ids  = [hcloud_ssh_key.main.id]
  network_id   = module.network.network_id
  subnet_id    = module.network.subnet_id # FIX: depends_on via a variable
  private_ip   = var.master_private_ip
  firewall_ids = [module.firewall.k3s_firewall_id]

  labels = {
    project = var.project_name
    role    = "master"
  }
}

# ─── k3s Worker 1 ─────────────────────────────────────────────────────────────
module "k3s_worker_1" {
  source = "./modules/vm"

  name         = "${var.project_name}-worker-1"
  server_type  = var.k3s_server_type
  location     = var.location
  image        = var.os_image
  ssh_key_ids  = [hcloud_ssh_key.main.id]
  network_id   = module.network.network_id
  subnet_id    = module.network.subnet_id
  private_ip   = var.worker1_private_ip
  firewall_ids = [module.firewall.k3s_firewall_id]

  labels = {
    project = var.project_name
    role    = "worker"
  }
}

# ─── k3s Worker 2 ─────────────────────────────────────────────────────────────
module "k3s_worker_2" {
  source = "./modules/vm"

  name         = "${var.project_name}-worker-2"
  server_type  = var.k3s_server_type
  location     = var.location
  image        = var.os_image
  ssh_key_ids  = [hcloud_ssh_key.main.id]
  network_id   = module.network.network_id
  subnet_id    = module.network.subnet_id
  private_ip   = var.worker2_private_ip
  firewall_ids = [module.firewall.k3s_firewall_id]

  labels = {
    project = var.project_name
    role    = "worker"
  }
}

# ─── ELK (Elasticsearch + Logstash + Kibana) ──────────────────────────────────
module "elk" {
  source = "./modules/vm"

  name         = "${var.project_name}-elk"
  server_type  = var.elk_server_type
  location     = var.location
  image        = var.os_image
  ssh_key_ids  = [hcloud_ssh_key.main.id]
  network_id   = module.network.network_id
  subnet_id    = module.network.subnet_id
  private_ip   = var.elk_private_ip
  firewall_ids = [module.firewall.elk_firewall_id]

  labels = {
    project = var.project_name
    role    = "elk"
  }
}

# ─── PostgreSQL ───────────────────────────────────────────────────────────────
module "postgres" {
  source = "./modules/vm"

  name         = "${var.project_name}-postgres"
  server_type  = var.db_server_type
  location     = var.location
  image        = var.os_image
  ssh_key_ids  = [hcloud_ssh_key.main.id]
  network_id   = module.network.network_id
  subnet_id    = module.network.subnet_id
  private_ip   = var.postgres_private_ip
  firewall_ids = [module.firewall.db_firewall_id]

  labels = {
    project = var.project_name
    role    = "postgres"
  }
}
