-- BigLake external table over curated/quotes-l1/**
-- Level 1 quotes: best bid/ask per symbol per tick
-- Partition columns decoded from Hive-style path segments (/key=value/)
-- Schema auto-detected from Parquet; explicit columns documented below:
--   ts_event TIMESTAMP, ts_received TIMESTAMP, symbol STRING, asset_class STRING,
--   exchange STRING, bid_price INT64, bid_volume INT64, ask_price INT64,
--   ask_volume INT64, seq INT64
-- NOTE: require_hive_partition_filter = false is intentional for Phase 02 ease of querying;
--       set true in production for cost safety.
CREATE OR REPLACE EXTERNAL TABLE `{{ project_id }}.vnmarket.quotes_l1`
WITH PARTITION COLUMNS (
    date DATE,
    asset_class STRING,
    symbol STRING
)
WITH CONNECTION `{{ project_id }}.asia-southeast1.gcs-vnmarket`
OPTIONS (
    format = 'PARQUET',
    hive_partition_uri_prefix
    = 'gs://vn-market-lake-{{ env }}/curated/quotes-l1/',
    uris = ['gs://vn-market-lake-{{ env }}/curated/quotes-l1/*'],
    require_hive_partition_filter = false
);
