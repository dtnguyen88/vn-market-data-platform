output "id" {
  value       = google_monitoring_alert_policy.policy.id
  description = "Alert policy resource ID."
}

output "name" {
  value       = google_monitoring_alert_policy.policy.name
  description = "Alert policy display name."
}
