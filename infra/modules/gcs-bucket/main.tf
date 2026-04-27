terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

resource "google_storage_bucket" "bucket" {
  project                     = var.project_id
  name                        = var.name
  location                    = var.location
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = var.versioning
  }

  lifecycle_rule {
    condition {
      with_state                 = "ARCHIVED"
      num_newer_versions         = 1
      days_since_noncurrent_time = var.noncurrent_age_days
    }
    action {
      type = "Delete"
    }
  }
}
