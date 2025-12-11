-- axi: true
SELECT
  id,
  customer_id,
  amount,
  status,
  COUNT(*) as order_count,
  SUM(amount) as total_amount
FROM raw_orders
GROUP BY id, customer_id, amount, status
