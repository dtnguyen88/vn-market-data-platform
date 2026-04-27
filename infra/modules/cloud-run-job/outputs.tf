output "name" {
  value       = google_cloud_run_v2_job.job.name
  description = "Job name."
}

output "id" {
  value       = google_cloud_run_v2_job.job.id
  description = "Fully-qualified job resource ID."
}
