-- BigLake external table over curated/daily-ohlcv/**
-- Daily OHLCV bars: open, high, low, close, volume per symbol per trading day
-- Partition columns decoded from Hive-style path segments (/key=value/)
-- Schema auto-detected from Parquet; explicit columns documented below:
--   date DATE, symbol STRING, asset_class STRING, exchange STRING,
--   open INT64, high INT64, low INT64, close INT64, volume INT64,
--   value INT64, foreign_buy INT64, foreign_sell INT64
-- NOTE: require_hive_partition_filter = false is intentional for Phase 02 ease of querying;
--       set true in production for cost safety.
CREATE OR REPLACE EXTERNAL TABLE `{{ project_id }}.vnmarket.daily_ohlcv`
WITH PARTITION COLUMNS (
    year INT64
)
WITH CONNECTION `{{ project_id }}.asia-southeast1.gcs-vnmarket`
OPTIONS (
    format = 'PARQUET',
    hive_partition_uri_prefix
    = 'gs://vn-market-lake-{{ env }}/curated/daily-ohlcv/',
    uris = ['gs://vn-market-lake-{{ env }}/curated/daily-ohlcv/*'],
    require_hive_partition_filter = false
);
