-- BigLake external table over curated/fundamentals/**
-- Fundamentals: quarterly financial statements (IS, BS, CF) per listed company
-- Partition columns decoded from Hive-style path segments (/key=value/)
-- Quarter format: YYYYQN e.g. 2024Q1
-- Schema auto-detected from Parquet; explicit columns documented below:
--   symbol STRING, quarter STRING, report_type STRING, currency STRING,
--   revenue INT64, gross_profit INT64, operating_income INT64, net_income INT64,
--   total_assets INT64, total_equity INT64, total_debt INT64,
--   operating_cash_flow INT64, capex INT64, eps FLOAT64, bvps FLOAT64
-- NOTE: require_hive_partition_filter = false is intentional for Phase 02 ease of querying;
--       set true in production for cost safety.
CREATE OR REPLACE EXTERNAL TABLE `{{ project_id }}.vnmarket.fundamentals`
WITH PARTITION COLUMNS (
    quarter STRING
)
WITH CONNECTION `{{ project_id }}.asia-southeast1.gcs-vnmarket`
OPTIONS (
    format = 'PARQUET',
    hive_partition_uri_prefix
    = 'gs://vn-market-lake-{{ env }}/curated/fundamentals/',
    uris = ['gs://vn-market-lake-{{ env }}/curated/fundamentals/*'],
    require_hive_partition_filter = false
);
