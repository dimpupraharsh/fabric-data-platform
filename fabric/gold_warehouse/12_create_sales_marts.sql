-- These are materialized, certified gross-sales summaries. Each reads only
-- eligible Gold fact rows, so a date warning does not erase a valid sale.
IF OBJECT_ID('gold.mart_daily_sales', 'U') IS NULL
    CREATE TABLE gold.mart_daily_sales AS
    SELECT order_date,
           SUM(sales_amount) AS gross_sales_amount,
           SUM(CAST(quantity AS bigint)) AS units_sold,
           COUNT_BIG(*) AS sales_line_count,
           CAST(SUM(sales_amount) / NULLIF(SUM(CAST(quantity AS decimal(18,2))), 0)
                AS decimal(18,4)) AS average_selling_price
    FROM gold.fact_sales
    WHERE is_sales_eligible = 1
    GROUP BY order_date;
GO

IF OBJECT_ID('gold.mart_monthly_sales', 'U') IS NULL
    CREATE TABLE gold.mart_monthly_sales AS
    SELECT DATEFROMPARTS(YEAR(order_date), MONTH(order_date), 1) AS sales_month,
           SUM(gross_sales_amount) AS gross_sales_amount,
           SUM(units_sold) AS units_sold,
           SUM(sales_line_count) AS sales_line_count,
           CAST(SUM(gross_sales_amount) / NULLIF(SUM(CAST(units_sold AS decimal(18,2))), 0)
                AS decimal(18,4)) AS average_selling_price
    FROM gold.mart_daily_sales
    GROUP BY DATEFROMPARTS(YEAR(order_date), MONTH(order_date), 1);
GO

-- Stable entity keys collapse SCD2 versions without losing version keys on
-- the detail fact. This is spend by customer, not order frequency or LTV.
IF OBJECT_ID('gold.mart_customer_spend', 'U') IS NULL
    CREATE TABLE gold.mart_customer_spend AS
    SELECT customer_entity_key,
           SUM(sales_amount) AS gross_sales_amount,
           SUM(CAST(quantity AS bigint)) AS units_sold,
           COUNT_BIG(*) AS sales_line_count,
           MIN(order_date) AS first_sales_date,
           MAX(order_date) AS last_sales_date
    FROM gold.fact_sales
    WHERE is_sales_eligible = 1
    GROUP BY customer_entity_key;
GO

IF OBJECT_ID('gold.mart_product_performance', 'U') IS NULL
    CREATE TABLE gold.mart_product_performance AS
    SELECT product_entity_key,
           SUM(sales_amount) AS gross_sales_amount,
           SUM(CAST(quantity AS bigint)) AS units_sold,
           COUNT_BIG(*) AS sales_line_count
    FROM gold.fact_sales
    WHERE is_sales_eligible = 1
    GROUP BY product_entity_key;
GO

-- Category key is the one resolved on the historical sale. A later product
-- reclassification cannot silently rewrite prior category totals.
IF OBJECT_ID('gold.mart_category_performance', 'U') IS NULL
    CREATE TABLE gold.mart_category_performance AS
    SELECT category_key,
           SUM(sales_amount) AS gross_sales_amount,
           SUM(CAST(quantity AS bigint)) AS units_sold,
           COUNT_BIG(*) AS sales_line_count
    FROM gold.fact_sales
    WHERE is_sales_eligible = 1
    GROUP BY category_key;
GO

-- Group on the location version key; the corresponding Gold dimension gives
-- the geography/zone attributes that were effective for those fact rows.
IF OBJECT_ID('gold.mart_geography_sales', 'U') IS NULL
    CREATE TABLE gold.mart_geography_sales AS
    SELECT location_key,
           SUM(sales_amount) AS gross_sales_amount,
           SUM(CAST(quantity AS bigint)) AS units_sold,
           COUNT_BIG(*) AS sales_line_count
    FROM gold.fact_sales
    WHERE is_sales_eligible = 1
    GROUP BY location_key;
GO

-- YoY uses complete 2020-2025 calendar years only. 2026 is partial and
-- belongs in an aligned YTD comparison, not this full-year metric.
IF OBJECT_ID('gold.mart_sales_yoy', 'U') IS NULL
    CREATE TABLE gold.mart_sales_yoy AS
    WITH annual AS (
        SELECT YEAR(order_date) AS sales_year,
               SUM(gross_sales_amount) AS gross_sales_amount,
               SUM(units_sold) AS units_sold
        FROM gold.mart_daily_sales
        WHERE order_date >= '2020-01-01' AND order_date < '2026-01-01'
        GROUP BY YEAR(order_date)
    )
    SELECT current_year.sales_year,
           current_year.gross_sales_amount,
           previous_year.gross_sales_amount AS prior_year_gross_sales_amount,
           current_year.units_sold,
           CAST(100.0 * (current_year.gross_sales_amount - previous_year.gross_sales_amount)
                / NULLIF(previous_year.gross_sales_amount, 0) AS decimal(18,4))
                AS gross_sales_yoy_pct
    FROM annual AS current_year
    INNER JOIN annual AS previous_year
      ON previous_year.sales_year = current_year.sales_year - 1;
GO
