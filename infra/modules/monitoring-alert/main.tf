terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

resource "google_monitoring_alert_policy" "policy" {
  project      = var.project_id
  display_name = var.display_name
  combiner     = "OR"
  enabled      = true
  user_labels  = var.labels

  documentation {
    content   = var.documentation
    mime_type = "text/markdown"
  }

  conditions {
    display_name = var.display_name
    condition_threshold {
      filter          = var.filter
      duration        = "${var.duration_seconds}s"
      comparison      = var.comparison
      threshold_value = var.threshold_value
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.notification_channel_ids
}
