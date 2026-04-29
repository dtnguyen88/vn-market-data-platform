output "service_account_emails" {
  value       = module.service_accounts.emails
  description = "Map of SA short name to email for the staging environment."
}

output "secret_ids" {
  value       = module.secrets.secret_ids
  sensitive   = true
  description = "Map of secret name to Secret Manager resource ID for the staging environment."
}

output "lake_bucket" {
  value       = module.lake_bucket.name
  description = "GCS data-lake bucket name."
}

output "bigquery_dataset" {
  value       = google_bigquery_dataset.vnmarket.dataset_id
  description = "BigQuery dataset ID for vnmarket external tables."
}

output "bigquery_connection" {
  value       = google_bigquery_connection.gcs.id
  description = "Fully-qualified BigQuery Connection ID for BigLake."
}

output "pubsub_topics" {
  value = {
    ticks   = module.topic_ticks.topic_id
    l1      = module.topic_quotes_l1.topic_id
    l2      = module.topic_quotes_l2.topic_id
    indices = module.topic_indices.topic_id
  }
  description = "Map of stream → Pub/Sub topic ID for all 4 realtime streams."
}

output "pubsub_subscriptions" {
  value = {
    ticks   = module.topic_ticks.subscription_id
    l1      = module.topic_quotes_l1.subscription_id
    l2      = module.topic_quotes_l2.subscription_id
    indices = module.topic_indices.subscription_id
  }
  description = "Map of stream → subscription ID."
}

output "writer_urls" {
  value = {
    ticks   = module.writer_ticks.url
    l1      = module.writer_quotes_l1.url
    l2      = module.writer_quotes_l2.url
    indices = module.writer_indices.url
  }
  description = "Map of stream to parquet-writer Cloud Run service URL."
}

output "batch_jobs" {
  value = {
    eod       = module.batch_eod.id
    reference = module.batch_reference.id
  }
  description = "Map of batch Cloud Run Job names to fully-qualified resource IDs."
}

output "curate_job_id" {
  value       = module.curate_job.id
  description = "Curate Cloud Run Job resource ID."
}

output "workflows" {
  value = {
    shared_check_trading_day = module.wf_shared_check_trading_day.id
    eod_pipeline             = module.wf_eod_pipeline.id
    intraday_coverage_check  = module.wf_intraday_coverage_check.id
    reference_refresh        = module.wf_reference_refresh.id
    curate_fallback          = module.wf_curate_fallback.id
    calendar_refresh_yearly  = module.wf_calendar_refresh_yearly.id
    monthly_cost_report      = module.wf_monthly_cost_report.id
  }
  description = "Map of workflow short name to fully-qualified resource ID."
}

output "schedulers" {
  value = {
    eod_pipeline            = module.sched_eod_pipeline.id
    intraday_coverage_check = module.sched_intraday_coverage_check.id
    reference_refresh       = module.sched_reference_refresh.id
    curate_fallback         = module.sched_curate_fallback.id
    calendar_refresh_yearly = module.sched_calendar_refresh_yearly.id
    monthly_cost_report     = module.sched_monthly_cost_report.id
  }
  description = "Map of scheduler short name to job resource ID."
}

output "alerter_url" {
  value       = module.alerter_service.url
  description = "Telegram alerter Cloud Run service URL."
}

output "platform_alerts_topic" {
  value       = module.topic_platform_alerts.topic_id
  description = "Pub/Sub topic for all platform alerts."
}

output "alert_policies" {
  value = {
    # publisher_heartbeat   DISABLED — re-add after publisher Cloud Run is deployed
    topic_publish_zero   = module.alert_topic_publish_zero.id
    subscription_ack_lag = module.alert_subscription_ack_lag.id
  }
  description = "Map of alert-policy short name to resource ID."
}

output "research_app_url" {
  value       = module.research_app.url
  description = "Streamlit research-app Cloud Run URL (IAM-protected)."
}

output "ops_jobs" {
  value = {
    cost_report    = module.ops_cost_report.id
    dlq_drain      = module.ops_dlq_drain.id
    dlq_replay     = module.ops_dlq_replay.id
    coverage_check = module.ops_coverage_check.id
    data_quality   = module.ops_data_quality.id
  }
  description = "Map of ops job short name to Cloud Run Job ID."
}

output "monitoring_dashboard_id" {
  value       = module.monitoring_dashboard.id
  description = "vn-platform-ops Cloud Monitoring dashboard resource ID."
}

output "backfill_job_id" {
  value       = module.backfill_job.id
  description = "Backfill Cloud Run Job resource ID."
}
