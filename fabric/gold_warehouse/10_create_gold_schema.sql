-- Gold is a separate serving warehouse; source data remains in Silver.
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'gold')
    EXEC('CREATE SCHEMA gold');
GO

-- Historical category keys are retained so product reclassification does not
-- rewrite old category performance.
IF OBJECT_ID('gold.dim_category', 'U') IS NULL
    CREATE TABLE gold.dim_category AS
    SELECT category_key, category, subcategory
    FROM [lh_retail_silver].[conformed].[dim_category];
GO

IF OBJECT_ID('gold.dim_customer', 'U') IS NULL
    CREATE TABLE gold.dim_customer AS
    SELECT customer_key, customer_entity_key, customer_id,
           customer_business_key, first_name, last_name, country,
           location_entity_key, dwh_effective_from, dwh_effective_to,
           dwh_is_current, dwh_is_inferred
    FROM [lh_retail_silver].[conformed].[dim_customer];
GO

IF OBJECT_ID('gold.dim_product', 'U') IS NULL
    CREATE TABLE gold.dim_product AS
    SELECT product_key, product_entity_key, product_business_key,
           product_name, product_line, category_key, category,
           subcategory, dwh_effective_from, dwh_effective_to,
           dwh_is_current, dwh_is_inferred
    FROM [lh_retail_silver].[conformed].[dim_product];
GO

IF OBJECT_ID('gold.dim_location', 'U') IS NULL
    CREATE TABLE gold.dim_location AS
    SELECT location_key, location_entity_key, country, region,
           subregion, state_province, city, postal_code, market,
           sales_territory, delivery_zone, standard_sla_days,
           serviceability_flag, dwh_effective_from, dwh_effective_to,
           dwh_is_current, dwh_is_inferred
    FROM [lh_retail_silver].[conformed].[dim_location];
GO
