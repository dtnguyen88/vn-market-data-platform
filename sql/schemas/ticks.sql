-- BigLake external table over curated/ticks/**
-- Source: src/curate/ writes; raw at /raw/ticks/, curated at /curated/ticks/
-- Partition columns decoded from Hive-style path segments (/key=value/)
-- Schema auto-detected from Parquet; explicit columns documented below:
--   ts_event TIMESTAMP, ts_received TIMESTAMP, symbol STRING, asset_class STRING,
--   exchange STRING, price INT64, volume INT64, match_type STRING, side STRING,
--   trade_id STRING, seq INT64
-- NOTE: require_hive_partition_filter = false is intentional for Phase 02 ease of querying;
--       set true in production for cost safety.
CREATE OR REPLACE EXTERNAL TABLE `{{ project_id }}.vnmarket.ticks`
WITH PARTITION COLUMNS (
    date DATE,
    asset_class STRING,
    symbol STRING
)
WITH CONNECTION `{{ project_id }}.asia-southeast1.gcs-vnmarket`
OPTIONS (
    format = 'PARQUET',
    hive_partition_uri_prefix = 'gs://vn-market-lake-{{ env }}/curated/ticks/',
    uris = ['gs://vn-market-lake-{{ env }}/curated/ticks/*'],
    require_hive_partition_filter = false
);
