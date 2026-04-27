-- BigLake external table over curated/reference/futures_contracts/**
-- Futures contracts reference: listed futures contracts with contract specs
-- Partition columns decoded from Hive-style path segments (/key=value/)
-- Snapshot date = date the reference snapshot was captured (SCD Type 2 equivalent)
-- Writer must produce paths with snapshot=YYYY-MM-DD format for correct DATE parsing.
-- Schema auto-detected from Parquet; explicit columns documented below:
--   symbol STRING, underlying STRING, exchange STRING, contract_size INT64,
--   currency STRING, tick_size FLOAT64, tick_value FLOAT64,
--   first_trading_date DATE, last_trading_date DATE, settlement_date DATE,
--   settlement_type STRING, is_active BOOL
-- NOTE: require_hive_partition_filter = false is intentional for Phase 02 ease of querying;
--       set true in production for cost safety.
CREATE OR REPLACE EXTERNAL TABLE `{{ project_id }}.vnmarket.futures_contracts`
WITH PARTITION COLUMNS (
    snapshot DATE
)
WITH CONNECTION `{{ project_id }}.asia-southeast1.gcs-vnmarket`
OPTIONS (
    format = 'PARQUET',
    hive_partition_uri_prefix
    = 'gs://vn-market-lake-{{ env }}/curated/reference/futures_contracts/',
    uris
    = ['gs://vn-market-lake-{{ env }}/curated/reference/futures_contracts/*'],
    require_hive_partition_filter = false
);
