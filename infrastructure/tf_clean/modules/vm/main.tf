resource "hcloud_server" "vm" {
  name        = var.name
  server_type = var.server_type
  location    = var.location
  image       = var.image
  ssh_keys    = var.ssh_key_ids
  labels      = var.labels

  # FIX: firewall_ids takes a number, not a string
  firewall_ids = var.firewall_ids

  network {
    network_id = var.network_id
    ip         = var.private_ip
  }

  # FIX: explicit dependency on the subnet — the server is not created before the network is ready
  depends_on = [var.subnet_id]

  # Python3 is required by Ansible to run its modules
  user_data = <<-EOT
    #cloud-config
    package_update: true
    packages:
      - python3
  EOT
}
