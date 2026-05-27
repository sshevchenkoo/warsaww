variable "project_name" { type = string }
variable "your_ssh_ip"  { type = string }

# ─── Файрвол для k3s нод ──────────────────────────────────────────────────────
resource "hcloud_firewall" "k3s" {
  name = "${var.project_name}-k3s"

  # SSH — только с твоего IP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["${var.your_ssh_ip}/32"]
  }

  # HTTP/HTTPS — публичный доступ для ingress
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

  # k3s API (kubectl) — только с твоего IP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "6443"
    source_ips = ["${var.your_ssh_ip}/32"]
  }

  # Внутренняя сеть — всё разрешено между нодами
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

# ─── Файрвол для ELK ──────────────────────────────────────────────────────────
resource "hcloud_firewall" "elk" {
  name = "${var.project_name}-elk"

  # SSH — только с твоего IP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["${var.your_ssh_ip}/32"]
  }

  # Kibana UI — только с твоего IP (никакого публичного доступа)
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "5601"
    source_ips = ["${var.your_ssh_ip}/32"]
  }

  # Logstash (TCP JSON от Fluent Bit) — только из приватной сети k3s нод
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "5000"
    source_ips = ["10.0.1.0/24"]
  }
}

# ─── Файрвол для PostgreSQL ───────────────────────────────────────────────────
resource "hcloud_firewall" "db" {
  name = "${var.project_name}-db"

  # SSH — только с твоего IP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["${var.your_ssh_ip}/32"]
  }

  # PostgreSQL — только из приватной подсети, снаружи закрыт
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
