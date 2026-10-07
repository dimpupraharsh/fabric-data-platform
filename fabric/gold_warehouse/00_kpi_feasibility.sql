-- Read-only profile of Silver before defining certified Gold measures.
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'conformed'
  AND TABLE_NAME IN ('fact_sales', 'fact_order_event', 'fact_shipment_event',
                     'fact_payment_event', 'dim_product', 'dim_location')
ORDER BY TABLE_NAME, ORDINAL_POSITION;
GO

SELECT 'sales' AS subject, COUNT_BIG(*) AS row_count,
       MIN(order_date) AS min_date, MAX(order_date) AS max_date,
       SUM(CASE WHEN dq_sales_amount_mismatch = 1 THEN 1 ELSE 0 END) AS amount_mismatches,
       SUM(CASE WHEN dq_ship_before_order = 1 THEN 1 ELSE 0 END) AS ship_date_errors,
       SUM(CASE WHEN dq_due_before_order = 1 THEN 1 ELSE 0 END) AS due_date_errors,
       SUM(CASE WHEN customer_key IS NULL THEN 1 ELSE 0 END) AS missing_customer_key,
       SUM(CASE WHEN product_key IS NULL THEN 1 ELSE 0 END) AS missing_product_key,
       SUM(CASE WHEN location_key IS NULL THEN 1 ELSE 0 END) AS missing_location_key
FROM conformed.fact_sales;
GO

SELECT order_year, COUNT_BIG(*) AS sales_lines,
       COUNT(DISTINCT order_number) AS orders,
       MIN(order_date) AS first_order_date,
       MAX(order_date) AS last_order_date
FROM conformed.fact_sales GROUP BY order_year ORDER BY order_year;
GO

SELECT 'order' AS event_type, order_status AS event_status, COUNT_BIG(*) AS events,
       COUNT(DISTINCT order_number) AS orders,
       MIN(event_ts) AS min_event_ts, MAX(event_ts) AS max_event_ts
FROM conformed.fact_order_event GROUP BY order_status
UNION ALL
SELECT 'shipment', event_status, COUNT_BIG(*), COUNT(DISTINCT order_number), MIN(event_ts), MAX(event_ts)
FROM conformed.fact_shipment_event GROUP BY event_status
UNION ALL
SELECT 'payment', event_status, COUNT_BIG(*), COUNT(DISTINCT order_number), MIN(event_ts), MAX(event_ts)
FROM conformed.fact_payment_event GROUP BY event_status
ORDER BY event_type, event_status;
GO
