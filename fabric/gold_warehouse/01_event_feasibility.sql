-- The order status column is absent from the live SQL endpoint; count its rows only.
SELECT 'order' AS event_type, COUNT_BIG(*) AS events,
       COUNT(DISTINCT order_number) AS orders,
       MIN(event_ts) AS min_event_ts, MAX(event_ts) AS max_event_ts,
       SUM(CASE WHEN dwh_status_valid = 0 THEN 1 ELSE 0 END) AS invalid_status_rows
FROM conformed.fact_order_event
UNION ALL
SELECT 'shipment', COUNT_BIG(*), COUNT(DISTINCT order_number), MIN(event_ts), MAX(event_ts),
       SUM(CASE WHEN dwh_status_valid = 0 THEN 1 ELSE 0 END)
FROM conformed.fact_shipment_event
UNION ALL
SELECT 'payment', COUNT_BIG(*), COUNT(DISTINCT order_number), MIN(event_ts), MAX(event_ts),
       SUM(CASE WHEN dwh_status_valid = 0 THEN 1 ELSE 0 END)
FROM conformed.fact_payment_event;
GO

SELECT 'shipment' AS event_type, event_status, COUNT_BIG(*) AS events,
       COUNT(DISTINCT order_number) AS orders
FROM conformed.fact_shipment_event GROUP BY event_status
UNION ALL
SELECT 'payment', event_status, COUNT_BIG(*), COUNT(DISTINCT order_number)
FROM conformed.fact_payment_event GROUP BY event_status
ORDER BY event_type, event_status;
GO

SELECT 'shipment' AS event_type, COUNT_BIG(*) AS matched_events
FROM conformed.fact_shipment_event e
WHERE EXISTS (SELECT 1 FROM conformed.fact_sales s WHERE s.order_number=e.order_number)
UNION ALL
SELECT 'payment', COUNT_BIG(*)
FROM conformed.fact_payment_event e
WHERE EXISTS (SELECT 1 FROM conformed.fact_sales s WHERE s.order_number=e.order_number)
UNION ALL
SELECT 'order', COUNT_BIG(*)
FROM conformed.fact_order_event e
WHERE EXISTS (SELECT 1 FROM conformed.fact_sales s WHERE s.order_number=e.order_number);
GO
