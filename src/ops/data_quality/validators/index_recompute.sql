-- Compare reported VNINDEX vs simple recompute (placeholder; real recompute needs constituent weights)
SELECT date, COUNT(*) AS row_count
FROM `{{ project_id }}.vnmarket.index_values`
WHERE index_code = 'VNINDEX'
  AND date = CURRENT_DATE() - 1
GROUP BY date
HAVING COUNT(*) = 0;
