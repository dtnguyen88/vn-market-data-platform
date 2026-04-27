output "service_account_emails" {
  value = module.service_accounts.emails
}

output "secret_ids" {
  value     = module.secrets.secret_ids
  sensitive = true
}
