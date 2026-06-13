output "k3s_firewall_id" {
  description = "ID of the firewall for k3s nodes"
  value       = hcloud_firewall.k3s.id
}

output "db_firewall_id" {
  description = "ID of the firewall for PostgreSQL"
  value       = hcloud_firewall.db.id
}

output "elk_firewall_id" {
  description = "ID of the firewall for ELK"
  value       = hcloud_firewall.elk.id
}
