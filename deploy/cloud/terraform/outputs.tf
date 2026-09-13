# Save the kubeconfig:  terraform output -raw kubeconfig > ../../.kube/config-do
output "kubeconfig" {
  description = "Raw kubeconfig for the DOKS cluster"
  value       = digitalocean_kubernetes_cluster.main.kube_config[0].raw_config
  sensitive   = true
}

# SQLAlchemy/psycopg URL for the `events` DB over the private network (sslmode=require).
# Put this into the warsaw-secrets Secret as DATABASE_URL.
output "database_url" {
  description = "DATABASE_URL for the app (events db, private host)"
  sensitive   = true
  value = format(
    "postgresql+psycopg://%s:%s@%s:%d/events?sslmode=require",
    digitalocean_database_cluster.pg.user,
    digitalocean_database_cluster.pg.password,
    digitalocean_database_cluster.pg.private_host,
    digitalocean_database_cluster.pg.port,
  )
}

# Public URI (default db) for one-off admin tasks like CREATE EXTENSION vector.
output "database_admin_uri" {
  description = "Public connection URI (defaultdb) — for the one-time pgvector enable"
  sensitive   = true
  value       = digitalocean_database_cluster.pg.uri
}

output "elk_public_ip" {
  description = "ELK droplet public IP (SSH / Kibana :5601)"
  value       = digitalocean_droplet.elk.ipv4_address
}

output "elk_private_ip" {
  description = "ELK droplet private IP (Fluent Bit ships logs here :5044)"
  value       = digitalocean_droplet.elk.ipv4_address_private
}

output "cluster_id" {
  value = digitalocean_kubernetes_cluster.main.id
}
