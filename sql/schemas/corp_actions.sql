-- BigLake external table over curated/corp-actions/**
-- Corporate actions: dividends, stock splits, rights issues, mergers per symbol
-- Partition columns decoded from Hive-style path segments (/key=value/)
-- Schema auto-detected from Parquet; explicit columns documented below:
--   symbol STRING, action_type STRING, ex_date DATE, record_date DATE,
--   payment_date DATE, ratio FLOAT64, cash_amount INT64, currency STRING,
--   notes STRING
-- NOTE: require_hive_partition_filter = false is intentional for Phase 02 ease of querying;
--       set true in production for cost safety.
CREATE OR REPLACE EXTERNAL TABLE `{{ project_id }}.vnmarket.corp_actions`
WITH PARTITION COLUMNS (
    year INT64
)
WITH CONNECTION `{{ project_id }}.asia-southeast1.gcs-vnmarket`
OPTIONS (
    format = 'PARQUET',
    hive_partition_uri_prefix
    = 'gs://vn-market-lake-{{ env }}/curated/corp-actions/',
    uris = ['gs://vn-market-lake-{{ env }}/curated/corp-actions/*'],
    require_hive_partition_filter = false
);
