-- One row per Silver source_sales_key. Order identity is checked against the
-- complete-population header; the six controlled mismatches remain visible.
-- Gross booked sales is not recognized revenue or net of refunds/returns.
IF OBJECT_ID('gold.fact_sales', 'U') IS NULL
    CREATE TABLE gold.fact_sales AS
    SELECT s.sales_key, s.source_sales_key, s.order_number,
           customer_key, customer_entity_key, product_key,
           product_entity_key, category_key, location_key,
           location_entity_key, s.customer_id, product_business_key,
           s.order_date, s.ship_date, s.due_date,
           sales_amount, quantity, unit_price,
           dq_ship_before_order, dq_due_before_order,
           dq_sales_amount_mismatch, dwh_dq_status,
           CAST(CASE WHEN h.order_number IS NOT NULL
                     AND s.customer_id = h.customer_id
                     AND s.order_date = h.order_date
                     THEN 0 ELSE 1 END AS bit) AS dq_order_identity_mismatch,
           CAST(CASE WHEN sales_amount >= 0 AND unit_price >= 0
                     AND quantity > 0 AND dq_sales_amount_mismatch = 0
                     AND h.order_number IS NOT NULL
                     AND s.customer_id = h.customer_id
                     AND s.order_date = h.order_date
                     THEN 1 ELSE 0 END AS bit) AS is_sales_eligible,
           s.dwh_source_load_ts, s.dwh_silver_load_ts,
           s.dwh_record_hash
    FROM [lh_retail_silver].[conformed].[fact_sales] AS s
    LEFT JOIN [lh_retail_silver].[conformed].[fact_order] AS h
      ON h.order_number = s.order_number;
GO
