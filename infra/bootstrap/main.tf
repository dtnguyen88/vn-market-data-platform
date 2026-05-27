terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# (The bootstrap shell script handles project + billing + APIs + tf-state bucket
# + terraform-sa creation. This Terraform bootstrap is for additional non-script
# baseline resources we want managed by IaC.)

# Default Firestore for telegram-alerter dedup state.
resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
}

# Artifact Registry for Docker images.
resource "google_artifact_registry_repository" "vn_market" {
  location      = var.region
  repository_id = "vn-market"
  format        = "DOCKER"
  description   = "Docker images for vn-market-data-platform services"

  labels = {
    env = var.env
  }

  # Keep image accumulation bounded. Without this, every CI build adds ~1 GB
  # and the repo grew to 88 GB / 336 images before we added this policy.
  # Strategy:
  #   1) KEEP latest 15 per package — covers terraform-pinned tags during
  #      active iteration (we sometimes ship 5+ builds/day).
  #   2) DELETE untagged versions older than 1d — CI overwrites tags often,
  #      leaving dangling digests; these are pure waste.
  #   3) DELETE any version older than 30d — long-term ceiling.
  # GCP applies KEEP before DELETE, so pinned tags inside the latest-15
  # window are protected even if they match a DELETE condition.
  cleanup_policies {
    id     = "keep-latest-15"
    action = "KEEP"
    most_recent_versions {
      keep_count = 15
    }
  }
  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "86400s" # 1d grace
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "2592000s" # 30d ceiling
    }
  }
}
