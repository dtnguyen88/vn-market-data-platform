-- v_daily_factors: per-symbol per-date factors derived from daily_ohlcv.
-- Adds: daily_return = (close - prev_close) / prev_close,
--       adj_daily_return based on adj_close.
-- Regular VIEW (BigLake constraint per v_top_of_book).
CREATE OR REPLACE VIEW `{{ project_id }}.vnmarket.v_daily_factors` AS
SELECT
    date,
    symbol,
    asset_class,
    exchange,
    close,
    adj_close,
    volume,
    value,
    SAFE_DIVIDE(
        close - LAG(close) OVER (PARTITION BY symbol ORDER BY date),
        LAG(close) OVER (PARTITION BY symbol ORDER BY date)
    ) AS daily_return,
    SAFE_DIVIDE(
        adj_close - LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date),
        LAG(adj_close) OVER (PARTITION BY symbol ORDER BY date)
    ) AS adj_daily_return
FROM `{{ project_id }}.vnmarket.daily_ohlcv`;
