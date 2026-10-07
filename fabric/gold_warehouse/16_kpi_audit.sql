-- Durable audit snapshot for dashboard trust and pipeline diagnosis. These
-- figures define the denominators behind every certified order KPI.
IF OBJECT_ID('gold.kpi_audit', 'U') IS NULL
    CREATE TABLE gold.kpi_audit AS
    SELECT CAST(SYSUTCDATETIME() AS datetime2(6)) AS audited_at_utc,
           s.sales_line_count, s.distinct_sales_keys,
           s.eligible_sales_line_count, s.order_identity_mismatch_line_count,
           s.eligible_gross_booked_sales_amount,
           o.order_count, o.distinct_order_numbers,
           o.eligible_order_count, o.orders_without_lines,
           o.invalid_status_or_date_order_count,
           o.shipping_sla_eligible_order_count,
           d.daily_gross_booked_sales_amount,
           m.monthly_gross_booked_sales_amount,
           l.lifecycle_eligible_order_count,
           p.payment_eligible_order_count,
           sh.shipping_mart_order_count
    FROM (
        SELECT COUNT_BIG(*) AS sales_line_count,
               COUNT(DISTINCT source_sales_key) AS distinct_sales_keys,
               SUM(CASE WHEN is_sales_eligible = 1 THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS eligible_sales_line_count,
               SUM(CASE WHEN dq_order_identity_mismatch = 1 THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS order_identity_mismatch_line_count,
               SUM(CASE WHEN is_sales_eligible = 1 THEN sales_amount ELSE CAST(0 AS decimal(18,2)) END) AS eligible_gross_booked_sales_amount
        FROM gold.fact_sales
    ) AS s
    CROSS JOIN (
        SELECT COUNT_BIG(*) AS order_count,
               COUNT(DISTINCT order_number) AS distinct_order_numbers,
               SUM(CASE WHEN is_order_metric_eligible = 1 THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS eligible_order_count,
               SUM(CASE WHEN sales_line_count = 0 THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS orders_without_lines,
               SUM(CASE WHEN is_order_metric_eligible = 0 THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS invalid_status_or_date_order_count,
               SUM(CASE WHEN is_order_metric_eligible = 1 AND is_shipping_sla_eligible = 1 THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END) AS shipping_sla_eligible_order_count
        FROM gold.fact_order
    ) AS o
    CROSS JOIN (
        SELECT SUM(gross_sales_amount) AS daily_gross_booked_sales_amount
        FROM gold.mart_daily_sales
    ) AS d
    CROSS JOIN (
        SELECT SUM(gross_sales_amount) AS monthly_gross_booked_sales_amount
        FROM gold.mart_monthly_sales
    ) AS m
    CROSS JOIN (
        SELECT SUM(eligible_order_count) AS lifecycle_eligible_order_count
        FROM gold.mart_order_lifecycle
    ) AS l
    CROSS JOIN (
        SELECT SUM(order_count) AS payment_eligible_order_count
        FROM gold.mart_payment_status
    ) AS p
    CROSS JOIN (
        SELECT SUM(delivered_order_count) AS shipping_mart_order_count
        FROM gold.mart_shipping_sla
    ) AS sh;
GO

-- Fail publication when grain, coverage, or materialized KPI totals disagree.
-- Controlled dirty source lines are allowed but must stay below 0.01%.
IF EXISTS (
    SELECT 1 FROM gold.kpi_audit
    WHERE sales_line_count <> distinct_sales_keys
       OR order_count <> distinct_order_numbers
       OR orders_without_lines <> 0
       OR order_identity_mismatch_line_count > sales_line_count * 0.0001
       OR ABS(eligible_gross_booked_sales_amount - daily_gross_booked_sales_amount) > 0.01
       OR ABS(eligible_gross_booked_sales_amount - monthly_gross_booked_sales_amount) > 0.01
       OR eligible_order_count <> lifecycle_eligible_order_count
       OR eligible_order_count <> payment_eligible_order_count
       OR shipping_sla_eligible_order_count <> shipping_mart_order_count
)
    RAISERROR('Gold KPI audit failed: grain, identity, coverage, or mart reconciliation differs.', 16, 1);
GO
