terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# ── Static External IP ───────────────────────────────────────────────────────
resource "google_compute_address" "innovacx_ip" {
  name   = "innovacx-static-ip"
  region = var.region
}

# ── Firewall Rule ────────────────────────────────────────────────────────────
resource "google_compute_firewall" "innovacx_ports" {
  name    = "innovacx-ports"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22", "80", "443", "5173", "8000", "8001", "8002", "3001"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["innovacx"]
}

# ── VM Instance ──────────────────────────────────────────────────────────────
resource "google_compute_instance" "innovacx_vm" {
  name         = "innovacx-vm"
  machine_type = "e2-standard-4"
  tags         = ["innovacx"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 80
      type  = "pd-balanced"
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.innovacx_ip.address
    }
  }

  # Startup script — runs once when the VM first boots
  metadata_startup_script = <<-EOF
    #!/bin/bash
    apt-get update -y
    apt-get install -y docker.io docker-compose-plugin git

    # Add the default user to the docker group
    usermod -aG docker $(getent passwd 1000 | cut -d: -f1)

    systemctl enable docker
    systemctl start docker
  EOF

  metadata = {
    ssh-keys = "${var.ssh_user}:${file(var.ssh_pub_key_path)}"
  }
}