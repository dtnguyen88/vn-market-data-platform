-- BigLake external table over curated/reference/tickers/**
-- Tickers reference: master list of all listed securities with metadata
-- Partition columns decoded from Hive-style path segments (/key=value/)
-- Snapshot date = date the reference snapshot was captured (SCD Type 2 equivalent)
-- Schema auto-detected from Parquet; explicit columns documented below:
--   symbol STRING, name STRING, name_en STRING, asset_class STRING,
--   exchange STRING, sector STRING, industry STRING, listing_date DATE,
--   delisting_date DATE, isin STRING, lot_size INT64, currency STRING,
--   is_active BOOL
-- NOTE: require_hive_partition_filter = false is intentional for Phase 02 ease of querying;
--       set true in production for cost safety.
CREATE OR REPLACE EXTERNAL TABLE `{{ project_id }}.vnmarket.tickers`
WITH PARTITION COLUMNS (
    snapshot DATE
)
WITH CONNECTION `{{ project_id }}.asia-southeast1.gcs-vnmarket`
OPTIONS (
    format = 'PARQUET',
    hive_partition_uri_prefix
    = 'gs://vn-market-lake-{{ env }}/curated/reference/tickers/',
    uris = ['gs://vn-market-lake-{{ env }}/curated/reference/tickers/*'],
    require_hive_partition_filter = false
);
