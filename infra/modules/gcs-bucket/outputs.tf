output "name" {
  value       = google_storage_bucket.bucket.name
  description = "Bucket name."
}

output "url" {
  value       = google_storage_bucket.bucket.url
  description = "gsutil-style gs://name URL."
}
