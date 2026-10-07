TRUNCATE TABLE retail_oi.customer_master RESTART IDENTITY;
TRUNCATE TABLE retail_oi.product_master RESTART IDENTITY;
TRUNCATE TABLE retail_oi.sales_order_line RESTART IDENTITY;
TRUNCATE TABLE retail_oi.order_status_event RESTART IDENTITY;
TRUNCATE TABLE retail_oi.shipment_status_event RESTART IDENTITY;
TRUNCATE TABLE retail_oi.payment_status_event RESTART IDENTITY;
TRUNCATE TABLE retail_oi.dq_rejects RESTART IDENTITY;
TRUNCATE TABLE retail_oi.source_simulation_run RESTART IDENTITY;
TRUNCATE TABLE retail_oi.watermark_control;
TRUNCATE TABLE retail_oi.number_series;

INSERT INTO retail_oi.watermark_control (source_table, watermark_column, last_watermark_val)
VALUES
    ('customer_master', 'dwh_load_ts', TIMESTAMPTZ '1900-01-01 00:00:00+00'),
    ('product_master', 'dwh_load_ts', TIMESTAMPTZ '1900-01-01 00:00:00+00'),
    ('sales_order_line', 'dwh_load_ts', TIMESTAMPTZ '1900-01-01 00:00:00+00'),
    ('order_status_event', 'dwh_load_ts', TIMESTAMPTZ '1900-01-01 00:00:00+00'),
    ('shipment_status_event', 'dwh_load_ts', TIMESTAMPTZ '1900-01-01 00:00:00+00'),
    ('payment_status_event', 'dwh_load_ts', TIMESTAMPTZ '1900-01-01 00:00:00+00');

INSERT INTO retail_oi.number_series (n)
SELECT generate_series(1, 500000);

WITH customer_candidates AS (
    SELECT
        c.cst_id AS customer_id,
        NULLIF(BTRIM(c.cst_key), '') AS customer_business_key,
        NULLIF(BTRIM(c.cst_firstname), '') AS first_name,
        NULLIF(BTRIM(c.cst_lastname), '') AS last_name,
        NULLIF(BTRIM(c.cst_marital_status), '') AS marital_status,
        COALESCE(NULLIF(BTRIM(a.gen), ''), NULLIF(BTRIM(c.cst_gndr), '')) AS gender,
        NULLIF(BTRIM(c.cst_create_date), '')::date AS create_date,
        NULLIF(BTRIM(a.bdate), '')::date AS birth_date,
        NULLIF(BTRIM(l.cntry), '') AS country,
        ROW_NUMBER() OVER (
            PARTITION BY c.cst_id
            ORDER BY
                CASE WHEN NULLIF(BTRIM(l.cntry), '') IS NOT NULL THEN 0 ELSE 1 END,
                CASE WHEN NULLIF(BTRIM(a.bdate), '') IS NOT NULL THEN 0 ELSE 1 END,
                NULLIF(BTRIM(c.cst_key), '')
        ) AS rn
    FROM retail_oi.stg_cust_info AS c
    LEFT JOIN retail_oi.stg_cust_az12 AS a
        ON REPLACE(BTRIM(a.cid), 'NAS', '') = BTRIM(c.cst_key)
    LEFT JOIN retail_oi.stg_loc_a101 AS l
        ON REPLACE(BTRIM(l.cid), '-', '') = BTRIM(c.cst_key)
    WHERE c.cst_id IS NOT NULL
)
INSERT INTO retail_oi.customer_master (
    customer_id,
    customer_business_key,
    first_name,
    last_name,
    marital_status,
    gender,
    create_date,
    birth_date,
    country
)
SELECT
    customer_id,
    customer_business_key,
    first_name,
    last_name,
    marital_status,
    gender,
    create_date,
    birth_date,
    country
FROM customer_candidates
WHERE rn = 1;

INSERT INTO retail_oi.product_master (
    product_id,
    product_business_key,
    product_name,
    product_cost,
    product_line,
    start_date,
    end_date,
    category,
    subcategory,
    maintenance_flag
)
SELECT DISTINCT
    p.prd_id,
    SUBSTRING(BTRIM(p.prd_key) FROM 7),
    NULLIF(BTRIM(p.prd_nm), ''),
    p.prd_cost,
    NULLIF(BTRIM(p.prd_line), ''),
    NULLIF(BTRIM(p.prd_start_dt), '')::date,
    NULLIF(BTRIM(p.prd_end_dt), '')::date,
    NULLIF(BTRIM(c.cat), ''),
    NULLIF(BTRIM(c.subcat), ''),
    NULLIF(BTRIM(c.maintenance), '')
FROM retail_oi.stg_prd_info AS p
LEFT JOIN retail_oi.stg_px_cat_g1v2 AS c
    ON c.id = REPLACE(LEFT(BTRIM(p.prd_key), 5), '-', '_')
WHERE p.prd_id IS NOT NULL
  AND NULLIF(BTRIM(p.prd_key), '') IS NOT NULL;

WITH parsed_sales AS (
    SELECT
        NULLIF(BTRIM(s.sls_ord_num), '') AS order_number,
        NULLIF(BTRIM(s.sls_prd_key), '') AS product_business_key,
        s.sls_cust_id AS customer_id,
        CASE
            WHEN s.sls_order_dt IS NULL OR s.sls_order_dt = 0 THEN NULL
            WHEN LPAD(s.sls_order_dt::text, 8, '0') !~ '^(19|20)[0-9]{6}$' THEN NULL
            WHEN TO_CHAR(TO_DATE(LPAD(s.sls_order_dt::text, 8, '0'), 'YYYYMMDD'), 'YYYYMMDD') <> LPAD(s.sls_order_dt::text, 8, '0') THEN NULL
            ELSE TO_DATE(LPAD(s.sls_order_dt::text, 8, '0'), 'YYYYMMDD')
        END AS order_date,
        CASE
            WHEN s.sls_ship_dt IS NULL OR s.sls_ship_dt = 0 THEN NULL
            WHEN LPAD(s.sls_ship_dt::text, 8, '0') !~ '^(19|20)[0-9]{6}$' THEN NULL
            WHEN TO_CHAR(TO_DATE(LPAD(s.sls_ship_dt::text, 8, '0'), 'YYYYMMDD'), 'YYYYMMDD') <> LPAD(s.sls_ship_dt::text, 8, '0') THEN NULL
            ELSE TO_DATE(LPAD(s.sls_ship_dt::text, 8, '0'), 'YYYYMMDD')
        END AS ship_date,
        CASE
            WHEN s.sls_due_dt IS NULL OR s.sls_due_dt = 0 THEN NULL
            WHEN LPAD(s.sls_due_dt::text, 8, '0') !~ '^(19|20)[0-9]{6}$' THEN NULL
            WHEN TO_CHAR(TO_DATE(LPAD(s.sls_due_dt::text, 8, '0'), 'YYYYMMDD'), 'YYYYMMDD') <> LPAD(s.sls_due_dt::text, 8, '0') THEN NULL
            ELSE TO_DATE(LPAD(s.sls_due_dt::text, 8, '0'), 'YYYYMMDD')
        END AS due_date,
        s.sls_sales AS sales_amount,
        s.sls_quantity AS quantity,
        s.sls_price AS unit_price
    FROM retail_oi.stg_sales_details AS s
)
INSERT INTO retail_oi.sales_order_line (
    order_number,
    product_business_key,
    customer_id,
    order_date,
    ship_date,
    due_date,
    sales_amount,
    quantity,
    unit_price
)
SELECT
    order_number,
    product_business_key,
    customer_id,
    order_date,
    ship_date,
    due_date,
    sales_amount,
    quantity,
    unit_price
FROM parsed_sales
WHERE order_number IS NOT NULL
  AND product_business_key IS NOT NULL
  AND customer_id IS NOT NULL
  AND order_date IS NOT NULL
  AND sales_amount IS NOT NULL
  AND quantity IS NOT NULL
  AND unit_price IS NOT NULL;
