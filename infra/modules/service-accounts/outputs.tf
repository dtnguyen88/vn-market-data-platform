output "emails" {
  value       = { for k, sa in google_service_account.sa : k => sa.email }
  description = "Map of short SA name (e.g. realtime-publisher) to fully-qualified service-account email."
}
