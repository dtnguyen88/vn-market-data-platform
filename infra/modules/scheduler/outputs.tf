output "id" {
  value       = google_cloud_scheduler_job.job.id
  description = "Scheduler job resource ID."
}

output "name" {
  value       = google_cloud_scheduler_job.job.name
  description = "Scheduler job name."
}
