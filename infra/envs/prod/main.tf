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
  name       = "vn-market-lake-prod"
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

resource "google_storage_bucket_object" "calendar" {
  for_each     = fileset("${path.module}/../../calendar", "vn-trading-days-*.json")
  bucket       = module.lake_bucket.name
  name         = "_ops/calendar/${replace(each.value, "vn-trading-days-", "")}"
  source       = "${path.module}/../../calendar/${each.value}"
  content_type = "application/json"
}

module "topic_ticks" {
  source     = "../../modules/pubsub-topic"
  project_id = var.project_id
  name       = "market-ticks"
}

module "topic_quotes_l1" {
  source     = "../../modules/pubsub-topic"
  project_id = var.project_id
  name       = "market-quotes-l1"
}

module "topic_quotes_l2" {
  source     = "../../modules/pubsub-topic"
  project_id = var.project_id
  name       = "market-quotes-l2"
}

module "topic_indices" {
  source     = "../../modules/pubsub-topic"
  project_id = var.project_id
  name       = "market-indices"
}

locals {
  artifact_registry_prefix = "asia-southeast1-docker.pkg.dev/${var.project_id}/vn-market"
  publisher_image          = "${local.artifact_registry_prefix}/publisher:latest"
  writers_image            = "${local.artifact_registry_prefix}/writers:latest"
  symbols_url_prefix       = "gs://${module.lake_bucket.name}/_ops/reference"
}

# ─── 4 publisher shards (stateful WS consumers, min=max=1) ───────────────────

module "publisher_shard_0" {
  source                = "../../modules/cloud-run-service"
  project_id            = var.project_id
  location              = var.region
  name                  = "realtime-publisher-shard-0"
  image                 = local.publisher_image
  service_account_email = module.service_accounts.emails["realtime-publisher"]
  min_instances         = 1
  max_instances         = 1
  memory                = "1Gi"
  cpu                   = "1"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
    SHARD          = "0"
    SYMBOLS_URL    = "${local.symbols_url_prefix}/symbols-shard-0.json"
  }
}

module "publisher_shard_1" {
  source                = "../../modules/cloud-run-service"
  project_id            = var.project_id
  location              = var.region
  name                  = "realtime-publisher-shard-1"
  image                 = local.publisher_image
  service_account_email = module.service_accounts.emails["realtime-publisher"]
  min_instances         = 1
  max_instances         = 1
  memory                = "1Gi"
  cpu                   = "1"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
    SHARD          = "1"
    SYMBOLS_URL    = "${local.symbols_url_prefix}/symbols-shard-1.json"
  }
}

module "publisher_shard_2" {
  source                = "../../modules/cloud-run-service"
  project_id            = var.project_id
  location              = var.region
  name                  = "realtime-publisher-shard-2"
  image                 = local.publisher_image
  service_account_email = module.service_accounts.emails["realtime-publisher"]
  min_instances         = 1
  max_instances         = 1
  memory                = "1Gi"
  cpu                   = "1"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
    SHARD          = "2"
    SYMBOLS_URL    = "${local.symbols_url_prefix}/symbols-shard-2.json"
  }
}

module "publisher_shard_3" {
  source                = "../../modules/cloud-run-service"
  project_id            = var.project_id
  location              = var.region
  name                  = "realtime-publisher-shard-3"
  image                 = local.publisher_image
  service_account_email = module.service_accounts.emails["realtime-publisher"]
  min_instances         = 1
  max_instances         = 1
  memory                = "1Gi"
  cpu                   = "1"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
    SHARD          = "3"
    SYMBOLS_URL    = "${local.symbols_url_prefix}/symbols-shard-3.json"
  }
}

# ─── 4 parquet writers (push subscribers, min=1 max=5) ───────────────────────

module "writer_ticks" {
  source                = "../../modules/cloud-run-service"
  project_id            = var.project_id
  location              = var.region
  name                  = "parquet-writer-ticks"
  image                 = local.writers_image
  service_account_email = module.service_accounts.emails["parquet-writer"]
  min_instances         = 1
  max_instances         = 5
  memory                = "1Gi"
  cpu                   = "1"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
    STREAM         = "ticks"
  }
}

module "writer_quotes_l1" {
  source                = "../../modules/cloud-run-service"
  project_id            = var.project_id
  location              = var.region
  name                  = "parquet-writer-quotes-l1"
  image                 = local.writers_image
  service_account_email = module.service_accounts.emails["parquet-writer"]
  min_instances         = 1
  max_instances         = 5
  memory                = "1Gi"
  cpu                   = "1"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
    STREAM         = "quotes-l1"
  }
}

module "writer_quotes_l2" {
  source                = "../../modules/cloud-run-service"
  project_id            = var.project_id
  location              = var.region
  name                  = "parquet-writer-quotes-l2"
  image                 = local.writers_image
  service_account_email = module.service_accounts.emails["parquet-writer"]
  min_instances         = 1
  max_instances         = 5
  memory                = "1Gi"
  cpu                   = "1"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
    STREAM         = "quotes-l2"
  }
}

module "writer_indices" {
  source                = "../../modules/cloud-run-service"
  project_id            = var.project_id
  location              = var.region
  name                  = "parquet-writer-indices"
  image                 = local.writers_image
  service_account_email = module.service_accounts.emails["parquet-writer"]
  min_instances         = 1
  max_instances         = 5
  memory                = "1Gi"
  cpu                   = "1"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
    STREAM         = "indices"
  }
}

# ─── Push subscriptions: Pub/Sub → writer Cloud Run services ─────────────────
# The pubsub-topic module creates pull subscriptions (*-sub) which remain
# harmless. These explicit push subscriptions are the active delivery path.

resource "google_pubsub_subscription" "writer_push_ticks" {
  project              = var.project_id
  name                 = "market-ticks-push-sub"
  topic                = module.topic_ticks.topic_id
  ack_deadline_seconds = 60

  push_config {
    push_endpoint = module.writer_ticks.url
    oidc_token {
      service_account_email = module.service_accounts.emails["parquet-writer"]
    }
  }

  dead_letter_policy {
    dead_letter_topic     = module.topic_ticks.dlq_topic_id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

resource "google_pubsub_subscription" "writer_push_quotes_l1" {
  project              = var.project_id
  name                 = "market-quotes-l1-push-sub"
  topic                = module.topic_quotes_l1.topic_id
  ack_deadline_seconds = 60

  push_config {
    push_endpoint = module.writer_quotes_l1.url
    oidc_token {
      service_account_email = module.service_accounts.emails["parquet-writer"]
    }
  }

  dead_letter_policy {
    dead_letter_topic     = module.topic_quotes_l1.dlq_topic_id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

resource "google_pubsub_subscription" "writer_push_quotes_l2" {
  project              = var.project_id
  name                 = "market-quotes-l2-push-sub"
  topic                = module.topic_quotes_l2.topic_id
  ack_deadline_seconds = 60

  push_config {
    push_endpoint = module.writer_quotes_l2.url
    oidc_token {
      service_account_email = module.service_accounts.emails["parquet-writer"]
    }
  }

  dead_letter_policy {
    dead_letter_topic     = module.topic_quotes_l2.dlq_topic_id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

resource "google_pubsub_subscription" "writer_push_indices" {
  project              = var.project_id
  name                 = "market-indices-push-sub"
  topic                = module.topic_indices.topic_id
  ack_deadline_seconds = 60

  push_config {
    push_endpoint = module.writer_indices.url
    oidc_token {
      service_account_email = module.service_accounts.emails["parquet-writer"]
    }
  }

  dead_letter_policy {
    dead_letter_topic     = module.topic_indices.dlq_topic_id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# ─── IAM: grant parquet-writer SA roles/run.invoker on each writer service ───
# Required so Pub/Sub can use the OIDC token to authenticate push requests.

resource "google_cloud_run_v2_service_iam_member" "pubsub_invoker_ticks" {
  project  = var.project_id
  location = var.region
  name     = module.writer_ticks.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.service_accounts.emails["parquet-writer"]}"
}

resource "google_cloud_run_v2_service_iam_member" "pubsub_invoker_quotes_l1" {
  project  = var.project_id
  location = var.region
  name     = module.writer_quotes_l1.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.service_accounts.emails["parquet-writer"]}"
}

resource "google_cloud_run_v2_service_iam_member" "pubsub_invoker_quotes_l2" {
  project  = var.project_id
  location = var.region
  name     = module.writer_quotes_l2.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.service_accounts.emails["parquet-writer"]}"
}

resource "google_cloud_run_v2_service_iam_member" "pubsub_invoker_indices" {
  project  = var.project_id
  location = var.region
  name     = module.writer_indices.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.service_accounts.emails["parquet-writer"]}"
}

# Per-shard symbol manifests for publishers to subscribe to.
# Source-of-truth in repo (infra/symbols/); operator regenerates when universe changes.
resource "google_storage_bucket_object" "symbols" {
  for_each     = fileset("${path.module}/../../symbols", "symbols-shard-*.json")
  bucket       = module.lake_bucket.name
  name         = "_ops/reference/${each.value}"
  source       = "${path.module}/../../symbols/${each.value}"
  content_type = "application/json"
}
