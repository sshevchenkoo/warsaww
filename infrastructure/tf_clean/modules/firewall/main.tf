variable "project_name" { type = string }
variable "your_ssh_ip" { type = string }

# ─── Firewall for k3s nodes ───────────────────────────────────────────────────
resource "hcloud_firewall" "k3s" {
  name = "${var.project_name}-k3s"

  # SSH — only from your IP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["${var.your_ssh_ip}/32"]
  }

  # HTTP/HTTPS — public access for ingress
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # k3s API (kubectl) — only from your IP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "6443"
    source_ips = ["${var.your_ssh_ip}/32"]
  }

  # Internal network — everything allowed between nodes
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "any"
    source_ips = ["10.0.1.0/24"]
  }

  rule {
    direction  = "in"
    protocol   = "udp"
    port       = "any"
    source_ips = ["10.0.1.0/24"]
  }
}

# ─── Firewall for ELK ─────────────────────────────────────────────────────────
resource "hcloud_firewall" "elk" {
  name = "${var.project_name}-elk"

  # SSH — only from your IP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["${var.your_ssh_ip}/32"]
  }

  # Kibana UI — only from your IP (no public access)
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "5601"
    source_ips = ["${var.your_ssh_ip}/32"]
  }

  # Logstash (TCP JSON from Fluent Bit) — only from the k3s private network
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "5000"
    source_ips = ["10.0.1.0/24"]
  }
}

# ─── Firewall for PostgreSQL ──────────────────────────────────────────────────
resource "hcloud_firewall" "db" {
  name = "${var.project_name}-db"

  # SSH — only from your IP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["${var.your_ssh_ip}/32"]
  }

  # PostgreSQL — only from the private subnet, closed externally
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "5432"
    source_ips = ["10.0.1.0/24"]
  }

  # postgres_exporter metrics — Prometheus scrapes from k3s nodes
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "9187"
    source_ips = ["10.0.1.0/24"]
  }
}
