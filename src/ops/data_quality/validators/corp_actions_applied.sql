-- Days where adj_close == close but a corp action existed on that day (= adjustment skipped)
SELECT d.date, d.symbol
FROM `{{ project_id }}.vnmarket.daily_ohlcv` d
JOIN `{{ project_id }}.vnmarket.corp_actions` ca
  ON d.symbol = ca.symbol AND d.date = ca.ex_date
WHERE d.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND d.adj_close = d.close
  AND ca.action_type IN ('split', 'dividend_stock', 'dividend_cash');
