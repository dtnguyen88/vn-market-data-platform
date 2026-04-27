output "service_account_emails" {
  value       = module.service_accounts.emails
  description = "Map of SA short name to email for the staging environment."
}

output "secret_ids" {
  value       = module.secrets.secret_ids
  sensitive   = true
  description = "Map of secret name to Secret Manager resource ID for the staging environment."
}

output "lake_bucket" {
  value       = module.lake_bucket.name
  description = "GCS data-lake bucket name."
}

output "bigquery_dataset" {
  value       = google_bigquery_dataset.vnmarket.dataset_id
  description = "BigQuery dataset ID for vnmarket external tables."
}

output "bigquery_connection" {
  value       = google_bigquery_connection.gcs.id
  description = "Fully-qualified BigQuery Connection ID for BigLake."
}
