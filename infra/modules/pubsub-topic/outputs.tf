output "topic_id" {
  value       = google_pubsub_topic.main.id
  description = "Fully-qualified topic resource ID (projects/.../topics/...)."
}

output "topic_name" {
  value       = google_pubsub_topic.main.name
  description = "Short topic name."
}

output "subscription_id" {
  value       = google_pubsub_subscription.main.id
  description = "Subscription resource ID."
}

output "dlq_topic_id" {
  value       = google_pubsub_topic.dlq.id
  description = "DLQ topic resource ID."
}
