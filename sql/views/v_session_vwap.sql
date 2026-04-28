-- v_session_vwap: per-symbol per-date volume-weighted average price from ticks.
-- vwap = SUM(price * volume) / SUM(volume).
-- Regular VIEW (BigLake constraint per v_top_of_book).
CREATE OR REPLACE VIEW `{{ project_id }}.vnmarket.v_session_vwap` AS
SELECT
    symbol,
    asset_class,
    exchange,
    date,
    SUM(price * volume) / NULLIF(SUM(volume), 0) AS vwap_price,
    SUM(volume) AS total_volume,
    COUNT(*) AS tick_count,
    MIN(ts_event) AS first_tick_ts,
    MAX(ts_event) AS last_tick_ts
FROM `{{ project_id }}.vnmarket.ticks`
GROUP BY symbol, asset_class, exchange, date;
