-- Gold Warehouse must be able to read the Silver SQL endpoint before loading.
SELECT TOP (1) source_sales_key, order_date, sales_amount
FROM [lh_retail_silver].[conformed].[fact_sales];
