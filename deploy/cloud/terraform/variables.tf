# The DigitalOcean API token is NOT a variable — the provider reads it from the
# DIGITALOCEAN_TOKEN env var (set in .env, exported by the Makefile).

variable "project_name" {
  description = "Prefix for all DO resources"
  type        = string
  default     = "warsaw"
}

variable "region" {
  description = "DO region — fra1 (Frankfurt) is closest to Poland"
  type        = string
  default     = "fra1"
}

variable "ssh_public_key" {
  description = "Public SSH key for the ELK droplet. Set via TF_VAR_ssh_public_key in .env (e.g. contents of .ssh/id_ed25519.pub)."
  type        = string
}

variable "admin_ip" {
  description = "Your public IP in CIDR form for SSH + Kibana access, e.g. 1.2.3.4/32 (curl ifconfig.me). Set via TF_VAR_admin_ip in .env."
  type        = string
}

# ─── DOKS node pool ───────────────────────────────────────────────────────────
variable "node_size" {
  description = "Worker node size (s-2vcpu-4gb ~ $24/mo each)"
  type        = string
  default     = "s-2vcpu-4gb"
}

variable "node_min" {
  description = "Min nodes (autoscale)"
  type        = number
  default     = 2
}

variable "node_max" {
  description = "Max nodes (autoscale)"
  type        = number
  default     = 3
}

# ─── Managed Postgres ─────────────────────────────────────────────────────────
variable "db_size" {
  description = "Managed PG node size (db-s-1vcpu-1gb ~ $15/mo)"
  type        = string
  default     = "db-s-1vcpu-1gb"
}

variable "db_version" {
  description = "PostgreSQL major version"
  type        = string
  default     = "16"
}

# ─── ELK droplet ──────────────────────────────────────────────────────────────
variable "elk_size" {
  description = "ELK droplet size (Elasticsearch needs RAM; s-4vcpu-8gb minimum)"
  type        = string
  default     = "s-4vcpu-8gb"
}

variable "elk_image" {
  description = "ELK droplet OS image"
  type        = string
  default     = "ubuntu-24-04-x64"
}

variable "vpc_cidr" {
  description = "Private VPC range"
  type        = string
  default     = "10.10.10.0/24"
}
