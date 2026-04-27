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
}
