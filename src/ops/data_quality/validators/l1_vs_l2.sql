-- L1 best-bid/ask vs L2 top level; flag mismatches
SELECT
  l1.symbol,
  l1.ts_event,
  l1.bid_price AS l1_bid,
  l2.bid_px_1  AS l2_bid
FROM `{{ project_id }}.vnmarket.quotes_l1` l1
JOIN `{{ project_id }}.vnmarket.quotes_l2` l2
  ON l1.symbol = l2.symbol AND l1.ts_event = l2.ts_event
WHERE l1.date = CURRENT_DATE() - 1
  AND l1.bid_price != l2.bid_px_1;
