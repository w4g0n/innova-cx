output "vm_external_ip" {
  description = "External IP address of the InnovaCX VM"
  value       = google_compute_address.innovacx_ip.address
}

output "frontend_url" {
  value = "http://${google_compute_address.innovacx_ip.address}:5173"
}

output "backend_url" {
  value = "http://${google_compute_address.innovacx_ip.address}:8000/docs"
}