-- One stable order header per order_number. The earliest persisted sales line
-- is the deterministic anchor for legacy synthetic orders whose header fields
-- were incorrectly generated independently on every line.
CREATE TABLE IF NOT EXISTS retail_oi.order_header (
    order_number VARCHAR(20) PRIMARY KEY,
    anchor_sales_key BIGINT NOT NULL UNIQUE,
    customer_id INT NOT NULL,
    order_date DATE NOT NULL,
    ship_date DATE,
    due_date DATE,
    dwh_load_ts TIMESTAMPTZ(3) NOT NULL,
    dwh_source_system VARCHAR(20) NOT NULL
);

INSERT INTO retail_oi.order_header (
    order_number, anchor_sales_key, customer_id, order_date,
    ship_date, due_date, dwh_load_ts, dwh_source_system
)
SELECT s.order_number, s.sales_key, s.customer_id, s.order_date,
       s.ship_date, s.due_date, CURRENT_TIMESTAMP(3), 'sim_repair'
FROM (
    SELECT order_number, MIN(sales_key) AS anchor_sales_key
    FROM retail_oi.sales_order_line
    GROUP BY order_number
) a
JOIN retail_oi.sales_order_line s ON s.sales_key = a.anchor_sales_key
ON CONFLICT (order_number) DO NOTHING;

ANALYZE retail_oi.order_header;
