-- Investigate whether a composite order identity can rescue order-based KPIs.
SELECT dwh_dq_status, COUNT_BIG(*) AS sales_lines
FROM conformed.fact_sales GROUP BY dwh_dq_status;
GO

SELECT TOP (12) order_number, COUNT_BIG(*) AS lines,
       COUNT(DISTINCT customer_id) AS customers,
       COUNT(DISTINCT order_date) AS dates,
       MIN(order_date) AS first_date, MAX(order_date) AS last_date
FROM conformed.fact_sales
GROUP BY order_number HAVING COUNT(DISTINCT customer_id) > 1
ORDER BY lines DESC;
GO

SELECT COUNT_BIG(*) AS composite_orders,
       SUM(CASE WHEN line_count > 1 THEN 1 ELSE 0 END) AS multiline_composite_orders,
       MAX(line_count) AS max_lines_per_composite_order
FROM (
  SELECT order_number, customer_id, order_date, COUNT_BIG(*) AS line_count
  FROM conformed.fact_sales
  GROUP BY order_number, customer_id, order_date
) x;
GO

SELECT TOP (10) order_number, customer_id, order_date,
       COUNT_BIG(*) AS line_count,
       COUNT(DISTINCT product_business_key) AS distinct_products
FROM conformed.fact_sales
GROUP BY order_number, customer_id, order_date
HAVING COUNT_BIG(*) > 1 ORDER BY line_count DESC;
GO
