-- axi: true
SELECT
  c.region,
  SUM(o.amount) as mrr
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status = 'active'
GROUP BY c.region
