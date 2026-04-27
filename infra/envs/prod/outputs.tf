output "service_account_emails" {
  value       = module.service_accounts.emails
  description = "Map of SA short name to email for the production environment."
}

output "secret_ids" {
  value       = module.secrets.secret_ids
  sensitive   = true
  description = "Map of secret name to Secret Manager resource ID for the production environment."
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

output "pubsub_topics" {
  value = {
    ticks   = module.topic_ticks.topic_id
    l1      = module.topic_quotes_l1.topic_id
    l2      = module.topic_quotes_l2.topic_id
    indices = module.topic_indices.topic_id
  }
  description = "Map of stream → Pub/Sub topic ID for all 4 realtime streams."
}

output "pubsub_subscriptions" {
  value = {
    ticks   = module.topic_ticks.subscription_id
    l1      = module.topic_quotes_l1.subscription_id
    l2      = module.topic_quotes_l2.subscription_id
    indices = module.topic_indices.subscription_id
  }
  description = "Map of stream → subscription ID."
}
