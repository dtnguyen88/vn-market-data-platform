terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

resource "google_cloud_run_v2_job" "job" {
  project  = var.project_id
  location = var.location
  name     = var.name

  template {
    parallelism = var.parallelism
    task_count  = var.task_count

    template {
      service_account = var.service_account_email
      timeout         = var.task_timeout
      max_retries     = var.max_retries

      containers {
        image = var.image
        resources {
          limits = {
            memory = var.memory
            cpu    = var.cpu
          }
        }
        dynamic "env" {
          for_each = var.env_vars
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }
}
