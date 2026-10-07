-- Header grain is one row per business order. Event facts are sampled and
-- must never be used as the denominator for company-wide order rates.
IF OBJECT_ID('gold.fact_order', 'U') IS NULL
    CREATE TABLE gold.fact_order AS
    SELECT h.order_key, h.order_number, h.anchor_sales_key,
           h.customer_id, s.customer_entity_key, s.location_key,
           h.order_date, h.ship_date, h.due_date, h.delivered_ts,
           h.payment_ts, h.order_status, h.shipment_status,
           h.payment_status, h.status_updated_ts,
           COALESCE(s.sales_line_count, CAST(0 AS bigint)) AS sales_line_count,
           COALESCE(s.eligible_sales_line_count, CAST(0 AS bigint)) AS eligible_sales_line_count,
           COALESCE(s.identity_mismatch_line_count, CAST(0 AS bigint)) AS identity_mismatch_line_count,
           COALESCE(s.gross_booked_sales_amount, CAST(0 AS decimal(18,2))) AS gross_booked_sales_amount,
           COALESCE(s.units_sold, CAST(0 AS bigint)) AS units_sold,
           CAST(CASE WHEN h.dwh_order_status_valid = 1
                         AND h.dwh_shipment_status_valid = 1
                         AND h.dwh_payment_status_valid = 1
                         AND h.dwh_due_date_valid = 1
                         AND h.dwh_delivery_date_valid = 1
                         AND COALESCE(s.sales_line_count, 0) > 0
                         AND COALESCE(s.identity_mismatch_line_count, 0) = 0
                     THEN 1 ELSE 0 END AS bit) AS is_order_metric_eligible,
           CAST(CASE WHEN h.order_status IN ('delivered', 'returned')
                         AND h.delivered_ts IS NOT NULL
                         AND h.due_date IS NOT NULL
                         AND h.dwh_due_date_valid = 1
                         AND h.dwh_delivery_date_valid = 1
                         AND COALESCE(s.identity_mismatch_line_count, 0) = 0
                     THEN 1 ELSE 0 END AS bit) AS is_shipping_sla_eligible,
           h.dwh_source_load_ts, h.dwh_silver_load_ts, h.dwh_record_hash
    FROM [lh_retail_silver].[conformed].[fact_order] AS h
    LEFT JOIN (
        SELECT order_number,
               COUNT_BIG(*) AS sales_line_count,
               SUM(CASE WHEN is_sales_eligible = 1 THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS eligible_sales_line_count,
               SUM(CASE WHEN is_sales_eligible = 1 THEN sales_amount ELSE CAST(0 AS decimal(18,2)) END) AS gross_booked_sales_amount,
               SUM(CASE WHEN is_sales_eligible = 1 THEN CAST(quantity AS bigint) ELSE CAST(0 AS bigint) END) AS units_sold,
               MIN(location_key) AS location_key,
               MIN(customer_entity_key) AS customer_entity_key,
               SUM(CASE WHEN dq_order_identity_mismatch = 1 THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS identity_mismatch_line_count
        FROM gold.fact_sales
        GROUP BY order_number
    ) AS s ON s.order_number = h.order_number;
GO

-- AOV is gross booked sales divided by eligible orders, never by line count.
-- Return and cancellation amounts remain booked amounts because no refunds
-- ledger or finance recognition policy exists in the source contract.
IF OBJECT_ID('gold.mart_order_lifecycle', 'U') IS NULL
    CREATE TABLE gold.mart_order_lifecycle AS
    SELECT order_date,
           COUNT_BIG(*) AS eligible_order_count,
           SUM(CASE WHEN order_status = 'created' THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS created_order_count,
           SUM(CASE WHEN order_status = 'packed' THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS packed_order_count,
           SUM(CASE WHEN order_status = 'shipped' THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS shipped_order_count,
           SUM(CASE WHEN order_status = 'delivered' THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS delivered_order_count,
           SUM(CASE WHEN order_status = 'cancelled' THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS cancelled_order_count,
           SUM(CASE WHEN order_status = 'returned' THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS returned_order_count,
           SUM(gross_booked_sales_amount) AS gross_booked_sales_amount,
           CAST(SUM(gross_booked_sales_amount) / NULLIF(COUNT_BIG(*), 0) AS decimal(18,4)) AS average_order_value,
           CAST(100.0 * SUM(CASE WHEN order_status = 'cancelled' THEN 1 ELSE 0 END)
                / NULLIF(COUNT_BIG(*), 0) AS decimal(18,4)) AS cancellation_rate_pct,
           CAST(100.0 * SUM(CASE WHEN order_status = 'returned' THEN 1 ELSE 0 END)
                / NULLIF(COUNT_BIG(*), 0) AS decimal(18,4)) AS return_rate_pct
    FROM gold.fact_order
    WHERE is_order_metric_eligible = 1
    GROUP BY order_date;
GO

-- SLA denominator: delivered/returned orders with a valid promised due date.
-- In-transit and cancelled orders are not silently counted as late deliveries.
IF OBJECT_ID('gold.mart_shipping_sla', 'U') IS NULL
    CREATE TABLE gold.mart_shipping_sla AS
    SELECT o.order_date, COALESCE(l.delivery_zone, 'unknown') AS delivery_zone,
           COUNT_BIG(*) AS delivered_order_count,
           SUM(CASE WHEN CAST(o.delivered_ts AS date) <= o.due_date THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS on_time_order_count,
           SUM(CASE WHEN CAST(o.delivered_ts AS date) > o.due_date THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS late_order_count,
           CAST(100.0 * SUM(CASE WHEN CAST(o.delivered_ts AS date) <= o.due_date THEN 1 ELSE 0 END)
                / NULLIF(COUNT_BIG(*), 0) AS decimal(18,4)) AS on_time_delivery_rate_pct,
           CAST(AVG(CAST(DATEDIFF(day, o.order_date, CAST(o.delivered_ts AS date)) AS decimal(18,4)))
                AS decimal(18,4)) AS average_delivery_days
    FROM gold.fact_order AS o
    LEFT JOIN gold.dim_location AS l ON l.location_key = o.location_key
    WHERE o.is_order_metric_eligible = 1 AND o.is_shipping_sla_eligible = 1
    GROUP BY o.order_date, COALESCE(l.delivery_zone, 'unknown');
GO

-- Counts are current payment states, not transaction/settlement amounts.
IF OBJECT_ID('gold.mart_payment_status', 'U') IS NULL
    CREATE TABLE gold.mart_payment_status AS
    SELECT order_date, payment_status,
           COUNT_BIG(*) AS order_count,
           SUM(gross_booked_sales_amount) AS gross_booked_sales_amount
    FROM gold.fact_order
    WHERE is_order_metric_eligible = 1
    GROUP BY order_date, payment_status;
GO

-- Stable customer entity keys make repeat-order counts SCD2-safe.
IF OBJECT_ID('gold.mart_customer_order_frequency', 'U') IS NULL
    CREATE TABLE gold.mart_customer_order_frequency AS
    SELECT customer_entity_key,
           COUNT_BIG(*) AS order_count,
           SUM(gross_booked_sales_amount) AS gross_booked_sales_amount,
           MIN(order_date) AS first_order_date,
           MAX(order_date) AS last_order_date,
           CAST(CASE WHEN COUNT_BIG(*) >= 2 THEN 1 ELSE 0 END AS bit) AS is_repeat_customer
    FROM gold.fact_order
    WHERE is_order_metric_eligible = 1 AND customer_entity_key IS NOT NULL
    GROUP BY customer_entity_key;
GO
