-- Check SCD surrogate-key uniqueness in copied Gold dimensions.
SELECT 'customer' AS dimension_name, COUNT_BIG(*) AS dimension_rows,
       COUNT(DISTINCT customer_key) AS unique_version_keys
FROM gold.dim_customer
UNION ALL
SELECT 'product', COUNT_BIG(*), COUNT(DISTINCT product_key)
FROM gold.dim_product
UNION ALL
SELECT 'category', COUNT_BIG(*), COUNT(DISTINCT category_key)
FROM gold.dim_category
UNION ALL
SELECT 'location', COUNT_BIG(*), COUNT(DISTINCT location_key)
FROM gold.dim_location;
GO

-- Check keys at the fact's distinct-key scale rather than multiplying 15M
-- lines through repeated dimension joins.
SELECT 'customer' AS dimension_name, COUNT_BIG(*) AS missing_fact_keys
FROM (SELECT DISTINCT customer_key FROM gold.fact_sales) f
LEFT JOIN gold.dim_customer d ON d.customer_key = f.customer_key
WHERE d.customer_key IS NULL
UNION ALL
SELECT 'product', COUNT_BIG(*)
FROM (SELECT DISTINCT product_key FROM gold.fact_sales) f
LEFT JOIN gold.dim_product d ON d.product_key = f.product_key
WHERE d.product_key IS NULL
UNION ALL
SELECT 'category', COUNT_BIG(*)
FROM (SELECT DISTINCT category_key FROM gold.fact_sales) f
LEFT JOIN gold.dim_category d ON d.category_key = f.category_key
WHERE d.category_key IS NULL
UNION ALL
SELECT 'location', COUNT_BIG(*)
FROM (SELECT DISTINCT location_key FROM gold.fact_sales) f
LEFT JOIN gold.dim_location d ON d.location_key = f.location_key
WHERE d.location_key IS NULL;
GO
