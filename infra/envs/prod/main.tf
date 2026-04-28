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
  workflows_path           = "${path.module}/../../workflows"
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

# ─── Batch ingestion Cloud Run Jobs ──────────────────────────────────────────

module "batch_eod" {
  source                = "../../modules/cloud-run-job"
  project_id            = var.project_id
  location              = var.region
  name                  = "batch-ingester-eod"
  image                 = "${local.artifact_registry_prefix}/batch-eod:latest"
  service_account_email = module.service_accounts.emails["batch-ingester"]
  task_count            = 1
  parallelism           = 1
  task_timeout          = "1800s"
  max_retries           = 3
  memory                = "2Gi"
  cpu                   = "1"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
  }
}

module "batch_reference" {
  source                = "../../modules/cloud-run-job"
  project_id            = var.project_id
  location              = var.region
  name                  = "batch-ingester-reference"
  image                 = "${local.artifact_registry_prefix}/batch-reference:latest"
  service_account_email = module.service_accounts.emails["batch-ingester"]
  task_count            = 1
  parallelism           = 1
  task_timeout          = "600s"
  max_retries           = 3
  memory                = "1Gi"
  cpu                   = "1"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
  }
}

# ─── Curate Cloud Run Job ─────────────────────────────────────────────────────

module "curate_job" {
  source                = "../../modules/cloud-run-job"
  project_id            = var.project_id
  location              = var.region
  name                  = "curate"
  image                 = "${local.artifact_registry_prefix}/curate:latest"
  service_account_email = module.service_accounts.emails["curate"]
  task_count            = 1
  parallelism           = 1
  task_timeout          = "1800s" # 30 min
  max_retries           = 3
  memory                = "4Gi" # curate is memory-heavy (Polars in-memory ops)
  cpu                   = "2"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
  }
}

# ─── Workflows ────────────────────────────────────────────────────────────────

module "wf_shared_check_trading_day" {
  source                = "../../modules/workflow"
  project_id            = var.project_id
  location              = var.region
  name                  = "_shared-check-trading-day"
  description           = "Reusable: check if a date is a VN trading day."
  source_file_path      = "${local.workflows_path}/_shared-check-trading-day.yaml"
  service_account_email = module.service_accounts.emails["workflows"]
  labels                = { env = "prod" }
}

module "wf_eod_pipeline" {
  source                = "../../modules/workflow"
  project_id            = var.project_id
  location              = var.region
  name                  = "eod-pipeline"
  description           = "EOD: batch-eod → parallel curate → telegram."
  source_file_path      = "${local.workflows_path}/eod-pipeline.yaml"
  service_account_email = module.service_accounts.emails["workflows"]
  labels                = { env = "prod" }
}

module "wf_intraday_coverage_check" {
  source                = "../../modules/workflow"
  project_id            = var.project_id
  location              = var.region
  name                  = "intraday-coverage-check"
  description           = "Every 5min during trading hours: ingest receipt coverage."
  source_file_path      = "${local.workflows_path}/intraday-coverage-check.yaml"
  service_account_email = module.service_accounts.emails["workflows"]
  labels                = { env = "prod" }
}

module "wf_reference_refresh" {
  source                = "../../modules/workflow"
  project_id            = var.project_id
  location              = var.region
  name                  = "reference-refresh"
  description           = "Daily ticker + futures master refresh."
  source_file_path      = "${local.workflows_path}/reference-refresh.yaml"
  service_account_email = module.service_accounts.emails["workflows"]
  labels                = { env = "prod" }
}

module "wf_curate_fallback" {
  source                = "../../modules/workflow"
  project_id            = var.project_id
  location              = var.region
  name                  = "curate-fallback"
  description           = "Re-runs curate streams idempotently as EOD safety net."
  source_file_path      = "${local.workflows_path}/curate-fallback.yaml"
  service_account_email = module.service_accounts.emails["workflows"]
  labels                = { env = "prod" }
}

module "wf_calendar_refresh_yearly" {
  source                = "../../modules/workflow"
  project_id            = var.project_id
  location              = var.region
  name                  = "calendar-refresh-yearly"
  description           = "Verifies next year's calendar JSON is in GCS."
  source_file_path      = "${local.workflows_path}/calendar-refresh-yearly.yaml"
  service_account_email = module.service_accounts.emails["workflows"]
  labels                = { env = "prod" }
}

module "wf_monthly_cost_report" {
  source                = "../../modules/workflow"
  project_id            = var.project_id
  location              = var.region
  name                  = "monthly-cost-report"
  description           = "Triggers cost-report job; posts to Telegram."
  source_file_path      = "${local.workflows_path}/monthly-cost-report.yaml"
  service_account_email = module.service_accounts.emails["workflows"]
  labels                = { env = "prod" }
}

# ─── Schedulers (6 — none for the shared sub-workflow) ───────────────────────

module "sched_eod_pipeline" {
  source                = "../../modules/scheduler"
  project_id            = var.project_id
  location              = var.region
  name                  = "eod-pipeline-cron"
  description           = "Trigger eod-pipeline 16:00 ICT weekdays."
  schedule              = "0 16 * * 1-5"
  target_workflow_id    = module.wf_eod_pipeline.id
  service_account_email = module.service_accounts.emails["workflows"]
  request_body          = jsonencode({ env = "prod" })
}

module "sched_intraday_coverage_check" {
  source                = "../../modules/scheduler"
  project_id            = var.project_id
  location              = var.region
  name                  = "intraday-coverage-check-cron"
  description           = "Every 5 min during trading hours."
  schedule              = "*/5 9-15 * * 1-5"
  target_workflow_id    = module.wf_intraday_coverage_check.id
  service_account_email = module.service_accounts.emails["workflows"]
  request_body          = jsonencode({ env = "prod" })
}

module "sched_reference_refresh" {
  source                = "../../modules/scheduler"
  project_id            = var.project_id
  location              = var.region
  name                  = "reference-refresh-cron"
  description           = "06:00 ICT weekdays."
  schedule              = "0 6 * * 1-5"
  target_workflow_id    = module.wf_reference_refresh.id
  service_account_email = module.service_accounts.emails["workflows"]
  request_body          = jsonencode({ env = "prod" })
}

module "sched_curate_fallback" {
  source                = "../../modules/scheduler"
  project_id            = var.project_id
  location              = var.region
  name                  = "curate-fallback-cron"
  description           = "17:00 ICT weekdays."
  schedule              = "0 17 * * 1-5"
  target_workflow_id    = module.wf_curate_fallback.id
  service_account_email = module.service_accounts.emails["workflows"]
  request_body          = jsonencode({ env = "prod" })
}

module "sched_calendar_refresh_yearly" {
  source                = "../../modules/scheduler"
  project_id            = var.project_id
  location              = var.region
  name                  = "calendar-refresh-yearly-cron"
  description           = "Dec 1 09:00 ICT yearly."
  schedule              = "0 9 1 12 *"
  target_workflow_id    = module.wf_calendar_refresh_yearly.id
  service_account_email = module.service_accounts.emails["workflows"]
  request_body          = jsonencode({ env = "prod" })
}

module "sched_monthly_cost_report" {
  source                = "../../modules/scheduler"
  project_id            = var.project_id
  location              = var.region
  name                  = "monthly-cost-report-cron"
  description           = "1st of month 09:00 ICT."
  schedule              = "0 9 1 * *"
  target_workflow_id    = module.wf_monthly_cost_report.id
  service_account_email = module.service_accounts.emails["workflows"]
  request_body          = jsonencode({ env = "prod" })
}

# ─── Alerter: Pub/Sub topic + Cloud Run service + push subscription ───────────

# Pub/Sub topic for all platform alerts (workflows + monitoring channels publish here)
module "topic_platform_alerts" {
  source     = "../../modules/pubsub-topic"
  project_id = var.project_id
  name       = "platform-alerts"
}

# Alerter Cloud Run service (HTTP push subscriber for the topic above)
module "alerter_service" {
  source                = "../../modules/cloud-run-service"
  project_id            = var.project_id
  location              = var.region
  name                  = "telegram-alerter"
  image                 = "${local.artifact_registry_prefix}/alerter:latest"
  service_account_email = module.service_accounts.emails["alerter"]
  min_instances         = 0
  max_instances         = 3
  memory                = "512Mi"
  cpu                   = "1"
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
  }
}

# Push subscription: platform-alerts → telegram-alerter
resource "google_pubsub_subscription" "alerter_push" {
  project              = var.project_id
  name                 = "platform-alerts-push-sub"
  topic                = module.topic_platform_alerts.topic_id
  ack_deadline_seconds = 30

  push_config {
    push_endpoint = module.alerter_service.url
    oidc_token {
      service_account_email = module.service_accounts.emails["alerter"]
    }
  }

  dead_letter_policy {
    dead_letter_topic     = module.topic_platform_alerts.dlq_topic_id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

resource "google_cloud_run_v2_service_iam_member" "alerter_invoker" {
  project  = var.project_id
  location = var.region
  name     = module.alerter_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.service_accounts.emails["alerter"]}"
}

# Notification channel: Pub/Sub. Cloud Monitoring publishes alerts here.
resource "google_monitoring_notification_channel" "platform_alerts" {
  project      = var.project_id
  display_name = "platform-alerts (Pub/Sub)"
  type         = "pubsub"
  labels = {
    topic = module.topic_platform_alerts.topic_id
  }
}

# ─── 3 alert policies (spec F7.3) ────────────────────────────────────────────

# 1. publisher_heartbeat absence > 90s
module "alert_publisher_heartbeat" {
  source                   = "../../modules/monitoring-alert"
  project_id               = var.project_id
  display_name             = "publisher heartbeat absent >90s"
  documentation            = "A realtime-publisher shard has not emitted a heartbeat metric for >90s during a trading session. Likely crash or WS disconnect."
  filter                   = "metric.type=\"custom.googleapis.com/publisher/heartbeat\" resource.type=\"global\""
  duration_seconds         = 90
  threshold_value          = 0.5
  comparison               = "COMPARISON_LT"
  notification_channel_ids = [google_monitoring_notification_channel.platform_alerts.id]
  labels                   = { severity = "critical", source = "publisher" }
}

# 2. topic publish rate = 0 for >120s
module "alert_topic_publish_zero" {
  source                   = "../../modules/monitoring-alert"
  project_id               = var.project_id
  display_name             = "market-ticks publish rate = 0 >120s"
  documentation            = "No messages published to market-ticks for 2+ min during a trading session. Publisher likely down."
  filter                   = "metric.type=\"pubsub.googleapis.com/topic/send_message_operation_count\" resource.type=\"pubsub_topic\" resource.label.\"topic_id\"=\"market-ticks\""
  duration_seconds         = 120
  threshold_value          = 0.1
  comparison               = "COMPARISON_LT"
  notification_channel_ids = [google_monitoring_notification_channel.platform_alerts.id]
  labels                   = { severity = "critical", source = "pubsub" }
}

# 3. subscription oldest_unacked_message_age > 180s
module "alert_subscription_ack_lag" {
  source                   = "../../modules/monitoring-alert"
  project_id               = var.project_id
  display_name             = "any subscription ack-lag >180s"
  documentation            = "A Pub/Sub subscription has unacked messages older than 180s. Writer service likely backlogged or crashed."
  filter                   = "metric.type=\"pubsub.googleapis.com/subscription/oldest_unacked_message_age\" resource.type=\"pubsub_subscription\""
  duration_seconds         = 180
  threshold_value          = 180
  comparison               = "COMPARISON_GT"
  notification_channel_ids = [google_monitoring_notification_channel.platform_alerts.id]
  labels                   = { severity = "warning", source = "pubsub" }
}

# ─── Research App: Streamlit UI (IAM-protected via run.invoker grant) ─────────

module "research_app" {
  source                = "../../modules/cloud-run-service"
  project_id            = var.project_id
  location              = var.region
  name                  = "research-app"
  image                 = "${local.artifact_registry_prefix}/research-app:latest"
  service_account_email = module.service_accounts.emails["research-app"]
  min_instances         = 0
  max_instances         = 3
  memory                = "1Gi"
  cpu                   = "1"
  ingress               = "INGRESS_TRAFFIC_ALL"
  port                  = 8080
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    ENV            = "prod"
  }
}
