variable "name" { type = string }
variable "server_type" { type = string }
variable "location" { type = string }
variable "image" { type = string }
variable "network_id" { type = string }
variable "private_ip" { type = string }

variable "ssh_key_ids" {
  type = list(number) # FIX: hcloud_ssh_key.id returns a number
}

# FIX: subnet_id is passed so Terraform knows about the dependency
variable "subnet_id" {
  type        = string
  description = "Subnet ID — used only for depends_on"
}

# FIX: firewall_ids is of type number (not string)
variable "firewall_ids" {
  type = list(number)
}

variable "labels" {
  description = "Server labels — used by the Ansible hcloud plugin for grouping"
  type        = map(string)
  default     = {}
}
