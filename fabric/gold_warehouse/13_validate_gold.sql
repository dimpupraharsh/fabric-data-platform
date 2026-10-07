-- Verify the physical Gold fact keeps Silver's line grain and applies only
-- the intended monetary eligibility rule.
SELECT 'gold_fact' AS object_name, COUNT_BIG(*) AS row_count,
       COUNT(DISTINCT source_sales_key) AS unique_source_sales_keys,
       SUM(CASE WHEN is_sales_eligible = 1 THEN 1 ELSE 0 END) AS eligible_lines,
       SUM(CASE WHEN is_sales_eligible = 0 THEN 1 ELSE 0 END) AS excluded_lines,
       SUM(CASE WHEN is_sales_eligible = 1 THEN sales_amount ELSE 0 END) AS eligible_gross_sales,
       SUM(CASE WHEN is_sales_eligible = 1 THEN CAST(quantity AS bigint) ELSE 0 END) AS eligible_units
FROM gold.fact_sales;
GO

SELECT 'daily' AS mart_name, COUNT_BIG(*) AS groups,
       SUM(gross_sales_amount) AS gross_sales_amount,
       SUM(units_sold) AS units_sold, SUM(sales_line_count) AS sales_line_count
FROM gold.mart_daily_sales
UNION ALL
SELECT 'monthly', COUNT_BIG(*), SUM(gross_sales_amount), SUM(units_sold), SUM(sales_line_count)
FROM gold.mart_monthly_sales
UNION ALL
SELECT 'customer', COUNT_BIG(*), SUM(gross_sales_amount), SUM(units_sold), SUM(sales_line_count)
FROM gold.mart_customer_spend
UNION ALL
SELECT 'product', COUNT_BIG(*), SUM(gross_sales_amount), SUM(units_sold), SUM(sales_line_count)
FROM gold.mart_product_performance
UNION ALL
SELECT 'category', COUNT_BIG(*), SUM(gross_sales_amount), SUM(units_sold), SUM(sales_line_count)
FROM gold.mart_category_performance
UNION ALL
SELECT 'geography', COUNT_BIG(*), SUM(gross_sales_amount), SUM(units_sold), SUM(sales_line_count)
FROM gold.mart_geography_sales;
GO

SELECT sales_year, gross_sales_amount, prior_year_gross_sales_amount,
       gross_sales_yoy_pct
FROM gold.mart_sales_yoy ORDER BY sales_year;
GO
