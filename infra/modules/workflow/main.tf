terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

resource "google_workflows_workflow" "wf" {
  project         = var.project_id
  region          = var.location
  name            = var.name
  description     = var.description
  service_account = var.service_account_email
  source_contents = file(var.source_file_path)
  labels          = var.labels
}
