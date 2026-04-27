output "name" {
  value       = google_cloud_run_v2_service.service.name
  description = "Cloud Run service short name."
}

output "url" {
  value       = google_cloud_run_v2_service.service.uri
  description = "Auto-assigned HTTPS URL of the deployed service."
}

output "service_id" {
  value       = google_cloud_run_v2_service.service.id
  description = "Fully-qualified service resource ID."
}
