terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

resource "google_pubsub_topic" "main" {
  project = var.project_id
  name    = var.name
}

resource "google_pubsub_topic" "dlq" {
  project = var.project_id
  name    = "${var.name}-dlq"
}

resource "google_pubsub_subscription" "main" {
  project              = var.project_id
  name                 = "${var.name}-sub"
  topic                = google_pubsub_topic.main.id
  ack_deadline_seconds = var.ack_deadline_seconds

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = var.max_delivery_attempts
  }

  retry_policy {
    minimum_backoff = var.minimum_backoff
    maximum_backoff = var.maximum_backoff
  }
}
