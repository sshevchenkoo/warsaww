output "public_ip" {
  description = "Public IPv4 address of the server"
  value       = hcloud_server.vm.ipv4_address
}

output "private_ip" {
  description = "Private IP in the Hetzner network"
  value       = var.private_ip
}

output "server_id" {
  description = "Server ID in Hetzner"
  value       = hcloud_server.vm.id
}
