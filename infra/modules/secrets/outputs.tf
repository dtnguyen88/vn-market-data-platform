output "secret_ids" {
  value       = { for k, s in google_secret_manager_secret.secret : k => s.id }
  description = "Map of secret name to fully-qualified Secret Manager resource ID."
}
