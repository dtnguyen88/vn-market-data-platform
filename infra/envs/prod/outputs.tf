output "service_account_emails" {
  value       = module.service_accounts.emails
  description = "Map of SA short name to email for the production environment."
}

output "secret_ids" {
  value       = module.secrets.secret_ids
  sensitive   = true
  description = "Map of secret name to Secret Manager resource ID for the production environment."
}
