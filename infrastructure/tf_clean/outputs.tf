output "master_public_ip" {
  description = "Публичный IP k3s мастера"
  value       = module.k3s_master.public_ip
}

output "worker_1_public_ip" {
  description = "Публичный IP k3s worker-1"
  value       = module.k3s_worker_1.public_ip
}

output "worker_2_public_ip" {
  description = "Публичный IP k3s worker-2"
  value       = module.k3s_worker_2.public_ip
}

output "postgres_public_ip" {
  description = "Публичный IP PostgreSQL (SSH доступ)"
  value       = module.postgres.public_ip
}

output "postgres_private_ip" {
  description = "Private IP of PostgreSQL — use in Django DATABASE_URL"
  value       = var.postgres_private_ip
}

output "elk_public_ip" {
  description = "Публичный IP ELK (Kibana UI: http://<ip>:5601)"
  value       = module.elk.public_ip
}

output "elk_private_ip" {
  description = "Приватный IP ELK — Logstash endpoint для Fluent Bit"
  value       = var.elk_private_ip
}

output "ssh_commands" {
  description = "Команды для подключения к серверам"
  value = {
    master   = "ssh root@${module.k3s_master.public_ip}"
    worker_1 = "ssh root@${module.k3s_worker_1.public_ip}"
    worker_2 = "ssh root@${module.k3s_worker_2.public_ip}"
    postgres = "ssh root@${module.postgres.public_ip}"
    elk      = "ssh root@${module.elk.public_ip}"
  }
}
