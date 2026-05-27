variable "hcloud_token" {
  description = "Hetzner Cloud API токен (hetzner.com → Security → API Tokens → Read & Write)"
  type        = string
  sensitive   = true
}

# FIX: один SSH ключ вместо двух — передаётся из Makefile
variable "ssh_public_key" {
  description = "Публичный SSH ключ из .ssh/id_ed25519.pub — передаётся через Makefile автоматически"
  type        = string
}

variable "project_name" {
  description = "Префикс для всех ресурсов в Hetzner"
  type        = string
  default     = "transcendence"
}

variable "location" {
  description = "Датацентр Hetzner: nbg1 (Нюрнберг), fsn1 (Фалькенштайн), hel1 (Хельсинки)"
  type        = string
  default     = "nbg1"
}

variable "k3s_server_type" {
  description = "Тип сервера для k3s нод (cx22 = 2 CPU, 4GB RAM ~4.5€/мес)"
  type        = string
  default     = "cx22"
}

variable "db_server_type" {
  description = "Тип сервера для PostgreSQL"
  type        = string
  default     = "cx22"
}

variable "your_ssh_ip" {
  description = "Твой публичный IP — только с него открыт SSH (узнать: curl ifconfig.me)"
  type        = string
}

variable "network_cidr" {
  description = "CIDR приватной сети Hetzner"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR подсети"
  type        = string
  default     = "10.0.1.0/24"
}

variable "network_zone" {
  description = "Зона сети Hetzner: eu-central, us-east, us-west, ap-southeast"
  type        = string
  default     = "eu-central"
}

variable "os_image" {
  description = "Образ ОС для всех VM"
  type        = string
  default     = "ubuntu-24.04"
}

variable "master_private_ip" {
  description = "Приватный IP k3s master ноды"
  type        = string
  default     = "10.0.1.10"
}

variable "worker1_private_ip" {
  description = "Приватный IP k3s worker-1"
  type        = string
  default     = "10.0.1.11"
}

variable "worker2_private_ip" {
  description = "Приватный IP k3s worker-2"
  type        = string
  default     = "10.0.1.12"
}

variable "postgres_private_ip" {
  description = "Приватный IP PostgreSQL ноды (должен совпадать с group_vars/all.yml → postgres_private_ip)"
  type        = string
  default     = "10.0.1.20"
}

variable "elk_server_type" {
  description = "Тип сервера для ELK (cx32 = 4 CPU, 8GB RAM — минимум для Elasticsearch)"
  type        = string
  default     = "cx32"
}

variable "elk_private_ip" {
  description = "Приватный IP ELK ноды"
  type        = string
  default     = "10.0.1.30"
}
