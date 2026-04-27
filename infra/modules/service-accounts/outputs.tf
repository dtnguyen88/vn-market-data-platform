output "emails" {
  value = { for k, sa in google_service_account.sa : k => sa.email }
}
