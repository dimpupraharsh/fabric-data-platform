-- Measure eligibility and grouping consistency for Gold sales KPIs.
SELECT COUNT_BIG(*) AS sales_lines,
       COUNT(DISTINCT source_sales_key) AS distinct_source_sales_keys,
       COUNT(DISTINCT order_number) AS distinct_orders,
       SUM(CASE WHEN sales_amount IS NULL OR sales_amount < 0 THEN 1 ELSE 0 END) AS invalid_amounts,
       SUM(CASE WHEN quantity IS NULL OR quantity <= 0 THEN 1 ELSE 0 END) AS invalid_quantities,
       SUM(CASE WHEN unit_price IS NULL OR unit_price < 0 THEN 1 ELSE 0 END) AS invalid_prices,
       SUM(CASE WHEN dwh_dq_status <> 'accepted' THEN 1 ELSE 0 END) AS nonaccepted_lines,
       SUM(CASE WHEN due_date IS NULL THEN 1 ELSE 0 END) AS missing_due_dates,
       SUM(CASE WHEN ship_date IS NULL THEN 1 ELSE 0 END) AS missing_ship_dates
FROM conformed.fact_sales;
GO

SELECT COUNT_BIG(*) AS orders,
       SUM(CASE WHEN customer_count > 1 THEN 1 ELSE 0 END) AS multi_customer_orders,
       SUM(CASE WHEN order_date_count > 1 THEN 1 ELSE 0 END) AS multi_order_date_orders,
       SUM(CASE WHEN due_date_count > 1 THEN 1 ELSE 0 END) AS multi_due_date_orders
FROM (
  SELECT order_number,
         COUNT(DISTINCT customer_key) AS customer_count,
         COUNT(DISTINCT order_date) AS order_date_count,
         COUNT(DISTINCT due_date) AS due_date_count
  FROM conformed.fact_sales GROUP BY order_number
) x;
GO

SELECT 'customer' AS dimension_name, COUNT_BIG(*) AS rows,
       SUM(CASE WHEN dwh_is_current = 1 THEN 1 ELSE 0 END) AS current_rows
FROM conformed.dim_customer
UNION ALL
SELECT 'product', COUNT_BIG(*), SUM(CASE WHEN dwh_is_current = 1 THEN 1 ELSE 0 END)
FROM conformed.dim_product
UNION ALL
SELECT 'location', COUNT_BIG(*), SUM(CASE WHEN dwh_is_current = 1 THEN 1 ELSE 0 END)
FROM conformed.dim_location;
GO
