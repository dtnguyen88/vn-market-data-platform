module "service_accounts" {
  source     = "../../modules/service-accounts"
  project_id = var.project_id
}

module "secrets" {
  source     = "../../modules/secrets"
  project_id = var.project_id
}

module "lake_bucket" {
  source     = "../../modules/gcs-bucket"
  project_id = var.project_id
  name       = "vn-market-lake-staging"
}

resource "google_bigquery_dataset" "vnmarket" {
  project       = var.project_id
  dataset_id    = "vnmarket"
  location      = var.region
  friendly_name = "VN Market Data (BigLake)"
}

resource "google_bigquery_connection" "gcs" {
  project       = var.project_id
  location      = var.region
  connection_id = "gcs-vnmarket"
  cloud_resource {}
}

# Connection's auto-created SA needs storage read on the bucket.
resource "google_storage_bucket_iam_member" "connection_reader" {
  bucket = module.lake_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_bigquery_connection.gcs.cloud_resource[0].service_account_id}"
}
