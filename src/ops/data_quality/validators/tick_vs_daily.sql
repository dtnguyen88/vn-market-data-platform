-- tick-volume sum per (symbol, date) vs daily.volume; flag mismatches >1%
SELECT
  t.symbol,
  t.date,
  t.tick_total_volume,
  d.volume AS daily_volume,
  SAFE_DIVIDE(ABS(t.tick_total_volume - d.volume), d.volume) AS rel_diff
FROM (
  SELECT symbol, date, SUM(volume) AS tick_total_volume
  FROM `{{ project_id }}.vnmarket.ticks`
  WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
  GROUP BY symbol, date
) t
JOIN `{{ project_id }}.vnmarket.daily_ohlcv` d
  ON t.symbol = d.symbol AND t.date = d.date
WHERE SAFE_DIVIDE(ABS(t.tick_total_volume - d.volume), d.volume) > 0.01;
