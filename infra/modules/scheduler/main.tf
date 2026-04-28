terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

resource "google_cloud_scheduler_job" "job" {
  project     = var.project_id
  region      = var.location
  name        = var.name
  description = var.description
  schedule    = var.schedule
  time_zone   = var.time_zone

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/${var.target_workflow_id}/executions"
    body = base64encode(jsonencode({
      argument = var.request_body
    }))
    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = var.service_account_email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}
