output "network_id" {
  description = "ID of the Hetzner private network"
  value       = hcloud_network.main.id
}

output "subnet_id" {
  description = "Subnet ID"
  value       = hcloud_network_subnet.main.id
}
