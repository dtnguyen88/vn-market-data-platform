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

  # Optional cold-tiering for data-lake buckets. Raw parquet is read often
  # for the first ~30d (intraday + recent-day analytics), rarely after.
  # daily_ohlcv_native is the hot read path for >30d history, so demoting
  # raw is safe.
  dynamic "lifecycle_rule" {
    for_each = var.tiering_enabled ? [1] : []
    content {
      condition {
        age                   = 30
        matches_storage_class = ["STANDARD"]
      }
      action {
        type          = "SetStorageClass"
        storage_class = "NEARLINE"
      }
    }
  }
  dynamic "lifecycle_rule" {
    for_each = var.tiering_enabled ? [1] : []
    content {
      condition {
        age                   = 90
        matches_storage_class = ["NEARLINE"]
      }
      action {
        type          = "SetStorageClass"
        storage_class = "COLDLINE"
      }
    }
  }
}
