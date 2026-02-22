variable "project_id" {
  description = "Your GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "me-central2"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "me-central2-a"
}

variable "ssh_user" {
  description = "Your Linux username for SSH access"
  type        = string
}

variable "ssh_pub_key_path" {
  description = "Path to your SSH public key file"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}