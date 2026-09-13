# Prod platform on DigitalOcean: a managed Kubernetes cluster (DOKS) for the app +
# monitoring, a managed Postgres (pgvector) outside the cluster, and one droplet for
# ELK.

data "digitalocean_kubernetes_versions" "current" {}

# ─── Private network shared by the cluster, the DB and the ELK droplet ─────────
resource "digitalocean_vpc" "main" {
  name     = "${var.project_name}-vpc"
  region   = var.region
  ip_range = var.vpc_cidr
}

resource "digitalocean_ssh_key" "main" {
  name       = "${var.project_name}-key"
  public_key = var.ssh_public_key
}

# ─── DOKS — managed control plane (free) + an autoscaling node pool ────────────
resource "digitalocean_kubernetes_cluster" "main" {
  name     = "${var.project_name}-cluster"
  region   = var.region
  version  = data.digitalocean_kubernetes_versions.current.latest_version
  vpc_uuid = digitalocean_vpc.main.id

  node_pool {
    name       = "${var.project_name}-pool"
    size       = var.node_size
    auto_scale = true
    min_nodes  = var.node_min
    max_nodes  = var.node_max
  }
}

# ─── Managed PostgreSQL (pgvector enabled once via CREATE EXTENSION, see runbook) ─
resource "digitalocean_database_cluster" "pg" {
  name                 = "${var.project_name}-pg"
  engine               = "pg"
  version              = var.db_version
  size                 = var.db_size
  region               = var.region
  node_count           = 1
  private_network_uuid = digitalocean_vpc.main.id
}

resource "digitalocean_database_db" "events" {
  cluster_id = digitalocean_database_cluster.pg.id
  name       = "events"
}

# The DOKS cluster (app) + your IP (one-off admin: CREATE EXTENSION vector) may reach the DB.
resource "digitalocean_database_firewall" "pg" {
  cluster_id = digitalocean_database_cluster.pg.id

  rule {
    type  = "k8s"
    value = digitalocean_kubernetes_cluster.main.id
  }
  rule {
    type  = "ip_addr"
    value = trimsuffix(var.admin_ip, "/32")
  }
}

# ─── ELK droplet (Elasticsearch + Logstash + Kibana), provisioned by Ansible ───
resource "digitalocean_droplet" "elk" {
  name     = "${var.project_name}-elk"
  region   = var.region
  size     = var.elk_size
  image    = var.elk_image
  vpc_uuid = digitalocean_vpc.main.id
  ssh_keys = [digitalocean_ssh_key.main.fingerprint]

  # Python3 for Ansible.
  user_data = <<-EOT
    #cloud-config
    package_update: true
    packages:
      - python3
  EOT
}

resource "digitalocean_firewall" "elk" {
  name        = "${var.project_name}-elk-fw"
  droplet_ids = [digitalocean_droplet.elk.id]

  # SSH + Kibana only from your IP.
  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = [var.admin_ip]
  }
  inbound_rule {
    protocol         = "tcp"
    port_range       = "5601"
    source_addresses = [var.admin_ip]
  }
  # Logstash TCP json_lines input from the cluster's Fluent Bit. Must allow the
  # DOKS cluster (pod) subnet, not just the VPC CIDR: Fluent Bit runs as pods
  # whose source IPs come from cluster_subnet (e.g. 10.114.0.0/16), and DOKS does
  # NOT SNAT pod traffic to the node's VPC IP — so a vpc_cidr-only rule silently
  # drops every log packet ("no upstream connections" in Fluent Bit) and nothing
  # ever reaches Elasticsearch.
  inbound_rule {
    protocol         = "tcp"
    port_range       = "5000"
    source_addresses = [var.vpc_cidr, digitalocean_kubernetes_cluster.main.cluster_subnet]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}
