-- v_top_of_book: most recent L1 quote per (symbol, date).
-- Definition: regular VIEW (not MATERIALIZED). Reason: BigLake external tables cannot
-- back materialized views in BigQuery. Revisit when (if) we move quotes_l1 to native BQ.
CREATE OR REPLACE VIEW `{{ project_id }}.vnmarket.v_top_of_book` AS
SELECT
    symbol,
    asset_class,
    exchange,
    date,
    ts_event AS last_ts,
    bid_price,
    bid_size,
    ask_price,
    ask_size,
    mid_price,
    spread_bps
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY symbol, date ORDER BY ts_event DESC) AS rn
    FROM `{{ project_id }}.vnmarket.quotes_l1`
)
WHERE rn = 1;
