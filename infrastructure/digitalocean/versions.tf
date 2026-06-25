terraform {
  # State is local by default. For an encrypted, lockable remote backend on DO
  # Spaces, see backend.tf.example (needs Terraform >= 1.6).
  required_version = ">= 1.5"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.40"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}
