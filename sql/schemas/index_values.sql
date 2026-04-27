-- BigLake external table over curated/indices/**
-- Index values: VN-Index, HNX-Index, UPCOM-Index intraday and EOD snapshots
-- Partition columns decoded from Hive-style path segments (/key=value/)
-- Schema auto-detected from Parquet; explicit columns documented below:
--   ts_event TIMESTAMP, index_code STRING, value FLOAT64, volume INT64,
--   value_change FLOAT64, pct_change FLOAT64, advances INT64, declines INT64,
--   unchanged INT64
-- NOTE: require_hive_partition_filter = false is intentional for Phase 02 ease of querying;
--       set true in production for cost safety.
CREATE OR REPLACE EXTERNAL TABLE `{{ project_id }}.vnmarket.index_values`
WITH PARTITION COLUMNS (
    date DATE,
    index_code STRING
)
WITH CONNECTION `{{ project_id }}.asia-southeast1.gcs-vnmarket`
OPTIONS (
    format = 'PARQUET',
    hive_partition_uri_prefix
    = 'gs://vn-market-lake-{{ env }}/curated/indices/',
    uris = ['gs://vn-market-lake-{{ env }}/curated/indices/*'],
    require_hive_partition_filter = false
);
