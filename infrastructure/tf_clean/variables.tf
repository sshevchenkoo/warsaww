variable "hcloud_token" {
  description = "Hetzner Cloud API token (hetzner.com → Security → API Tokens → Read & Write)"
  type        = string
  sensitive   = true
}

# FIX: a single SSH key instead of two — passed from the Makefile
variable "ssh_public_key" {
  description = "Public SSH key from .ssh/id_ed25519.pub — passed automatically via the Makefile"
  type        = string
}

variable "project_name" {
  description = "Prefix for all Hetzner resources"
  type        = string
  default     = "transcendence"
}

variable "location" {
  description = "Hetzner datacenter: nbg1 (Nuremberg), fsn1 (Falkenstein), hel1 (Helsinki)"
  type        = string
  default     = "nbg1"
}

variable "k3s_server_type" {
  description = "Server type for k3s nodes (cx22 = 2 CPU, 4GB RAM ~4.5€/mo)"
  type        = string
  default     = "cx22"
}

variable "db_server_type" {
  description = "Server type for PostgreSQL"
  type        = string
  default     = "cx22"
}

variable "your_ssh_ip" {
  description = "Your public IP — SSH is open only from it (find it: curl ifconfig.me)"
  type        = string
}

variable "network_cidr" {
  description = "CIDR of the Hetzner private network"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "Subnet CIDR"
  type        = string
  default     = "10.0.1.0/24"
}

variable "network_zone" {
  description = "Hetzner network zone: eu-central, us-east, us-west, ap-southeast"
  type        = string
  default     = "eu-central"
}

variable "os_image" {
  description = "OS image for all VMs"
  type        = string
  default     = "ubuntu-24.04"
}

variable "master_private_ip" {
  description = "Private IP of the k3s master node"
  type        = string
  default     = "10.0.1.10"
}

variable "worker1_private_ip" {
  description = "Private IP of k3s worker-1"
  type        = string
  default     = "10.0.1.11"
}

variable "worker2_private_ip" {
  description = "Private IP of k3s worker-2"
  type        = string
  default     = "10.0.1.12"
}

variable "postgres_private_ip" {
  description = "Private IP of the PostgreSQL node (must match group_vars/all.yml → postgres_private_ip)"
  type        = string
  default     = "10.0.1.20"
}

variable "elk_server_type" {
  description = "Server type for ELK (cx32 = 4 CPU, 8GB RAM — minimum for Elasticsearch)"
  type        = string
  default     = "cx32"
}

variable "elk_private_ip" {
  description = "Private IP of the ELK node"
  type        = string
  default     = "10.0.1.30"
}
