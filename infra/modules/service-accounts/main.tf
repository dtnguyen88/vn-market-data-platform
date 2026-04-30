terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

locals {
  service_accounts = {
    "realtime-publisher" = {
      display_name = "Realtime Publisher (SSI WS → Pub/Sub)"
      roles = [
        "roles/pubsub.publisher",
        "roles/secretmanager.secretAccessor",
        "roles/monitoring.metricWriter",
        "roles/logging.logWriter",
      ]
    }
    "parquet-writer" = {
      display_name = "Parquet Writer (Pub/Sub → GCS)"
      roles = [
        "roles/pubsub.subscriber",
        "roles/storage.objectAdmin",
        "roles/monitoring.metricWriter",
        "roles/logging.logWriter",
      ]
    }
    "batch-ingester" = {
      display_name = "Batch Ingester (vnstock → GCS)"
      roles = [
        "roles/storage.objectAdmin",
        "roles/secretmanager.secretAccessor",
        "roles/monitoring.metricWriter",
        "roles/logging.logWriter",
      ]
    }
    "curate" = {
      display_name = "Curate Layer Builder"
      roles = [
        "roles/storage.objectAdmin",
        "roles/bigquery.dataEditor",
        "roles/monitoring.metricWriter",
        "roles/logging.logWriter",
      ]
    }
    "alerter" = {
      display_name = "Telegram Alerter"
      roles = [
        "roles/pubsub.subscriber",
        "roles/secretmanager.secretAccessor",
        "roles/datastore.user", # Firestore dedup
        "roles/logging.logWriter",
      ]
    }
    "research-app" = {
      display_name = "Streamlit Research App"
      roles = [
        "roles/storage.objectViewer",
        "roles/bigquery.dataViewer",
        "roles/bigquery.jobUser",
        "roles/bigquery.readSessionUser",
        "roles/logging.logWriter",
      ]
    }
    "workflows" = {
      display_name = "Workflows Orchestrator"
      roles = [
        "roles/run.invoker",
        "roles/workflows.invoker",
        "roles/storage.objectViewer",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
      ]
    }
  }
}

resource "google_service_account" "sa" {
  for_each     = local.service_accounts
  account_id   = "${each.key}-sa"
  display_name = each.value.display_name
  project      = var.project_id
}

resource "google_project_iam_member" "binding" {
  for_each = merge([
    for sa_name, sa in local.service_accounts : {
      for role in sa.roles : "${sa_name}-${role}" => {
        sa_name = sa_name
        role    = role
      }
    }
  ]...)

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.sa[each.value.sa_name].email}"
}
