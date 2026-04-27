-- BigLake external table over curated/quotes-l2/**
-- Level 2 quotes: full order book depth (multiple bid/ask levels) per symbol
-- Partition columns decoded from Hive-style path segments (/key=value/)
-- Hour partition (0-23, 24-hour clock) enables sub-day pruning.
-- Writer must produce paths: /date=YYYY-MM-DD/asset_class=X/hour=H/symbol=SYM/
-- Schema auto-detected from Parquet; explicit columns documented below:
--   ts_event TIMESTAMP, ts_received TIMESTAMP, symbol STRING, asset_class STRING,
--   exchange STRING, level INT64, bid_price INT64, bid_volume INT64,
--   ask_price INT64, ask_volume INT64, seq INT64
-- NOTE: require_hive_partition_filter = false is intentional for Phase 02 ease of querying;
--       set true in production for cost safety.
CREATE OR REPLACE EXTERNAL TABLE `{{ project_id }}.vnmarket.quotes_l2`
WITH PARTITION COLUMNS (
    date DATE,
    asset_class STRING,
    hour INT64,
    symbol STRING
)
WITH CONNECTION `{{ project_id }}.asia-southeast1.gcs-vnmarket`
OPTIONS (
    format = 'PARQUET',
    hive_partition_uri_prefix
    = 'gs://vn-market-lake-{{ env }}/curated/quotes-l2/',
    uris = ['gs://vn-market-lake-{{ env }}/curated/quotes-l2/*'],
    require_hive_partition_filter = false
);
