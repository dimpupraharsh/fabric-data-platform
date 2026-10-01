-- Catalog-only export. Creates missing objects; never drops data or resets state.

IF SCHEMA_ID('gold') IS NULL EXEC('CREATE SCHEMA [gold]');
GO

IF OBJECT_ID('gold.dim_category', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[dim_category] (
    [category_key] bigint NULL,
    [category] varchar(8000) NULL,
    [subcategory] varchar(8000) NULL
  );
END;
GO

IF OBJECT_ID('gold.dim_customer', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[dim_customer] (
    [customer_key] bigint NULL,
    [customer_entity_key] bigint NULL,
    [customer_id] int NULL,
    [customer_business_key] varchar(8000) NULL,
    [first_name] varchar(8000) NULL,
    [last_name] varchar(8000) NULL,
    [country] varchar(8000) NULL,
    [location_entity_key] bigint NULL,
    [dwh_effective_from] datetime2(6) NULL,
    [dwh_effective_to] datetime2(6) NULL,
    [dwh_is_current] bit NULL,
    [dwh_is_inferred] bit NULL
  );
END;
GO

IF OBJECT_ID('gold.dim_customer_current', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[dim_customer_current] (
    [customer_entity_key] bigint NULL,
    [customer_id] int NULL,
    [customer_business_key] varchar(8000) NULL,
    [first_name] varchar(8000) NULL,
    [last_name] varchar(8000) NULL,
    [country] varchar(8000) NULL,
    [location_entity_key] bigint NULL
  );
END;
GO

IF OBJECT_ID('gold.dim_date', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[dim_date] (
    [calendar_date] date NULL,
    [calendar_year] int NULL,
    [calendar_quarter] int NULL,
    [calendar_month] int NULL,
    [month_name] varchar(20) NULL,
    [day_of_month] int NULL,
    [month_start_date] date NULL
  );
END;
GO

IF OBJECT_ID('gold.dim_location', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[dim_location] (
    [location_key] bigint NULL,
    [location_entity_key] bigint NULL,
    [country] varchar(8000) NULL,
    [region] varchar(8000) NULL,
    [subregion] varchar(8000) NULL,
    [state_province] varchar(8000) NULL,
    [city] varchar(8000) NULL,
    [postal_code] varchar(8000) NULL,
    [market] varchar(8000) NULL,
    [sales_territory] varchar(8000) NULL,
    [delivery_zone] varchar(8000) NULL,
    [standard_sla_days] int NULL,
    [serviceability_flag] bit NULL,
    [dwh_effective_from] datetime2(6) NULL,
    [dwh_effective_to] datetime2(6) NULL,
    [dwh_is_current] bit NULL,
    [dwh_is_inferred] bit NULL
  );
END;
GO

IF OBJECT_ID('gold.dim_product', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[dim_product] (
    [product_key] bigint NULL,
    [product_entity_key] bigint NULL,
    [product_business_key] varchar(8000) NULL,
    [product_name] varchar(8000) NULL,
    [product_line] varchar(8000) NULL,
    [category_key] bigint NULL,
    [category] varchar(8000) NULL,
    [subcategory] varchar(8000) NULL,
    [dwh_effective_from] datetime2(6) NULL,
    [dwh_effective_to] datetime2(6) NULL,
    [dwh_is_current] bit NULL,
    [dwh_is_inferred] bit NULL
  );
END;
GO

IF OBJECT_ID('gold.fact_order', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[fact_order] (
    [order_key] bigint NULL,
    [order_number] varchar(8000) NULL,
    [anchor_sales_key] bigint NULL,
    [customer_id] int NULL,
    [customer_entity_key] bigint NULL,
    [location_key] bigint NULL,
    [order_date] date NULL,
    [ship_date] date NULL,
    [due_date] date NULL,
    [delivered_ts] datetime2(6) NULL,
    [payment_ts] datetime2(6) NULL,
    [order_status] varchar(8000) NULL,
    [shipment_status] varchar(8000) NULL,
    [payment_status] varchar(8000) NULL,
    [status_updated_ts] datetime2(6) NULL,
    [sales_line_count] bigint NULL,
    [eligible_sales_line_count] bigint NULL,
    [identity_mismatch_line_count] bigint NULL,
    [gross_booked_sales_amount] decimal(38,2) NULL,
    [units_sold] bigint NULL,
    [is_order_metric_eligible] bit NULL,
    [is_shipping_sla_eligible] bit NULL,
    [dwh_source_load_ts] datetime2(6) NULL,
    [dwh_silver_load_ts] datetime2(6) NULL,
    [dwh_record_hash] varchar(8000) NULL
  );
END;
GO

IF OBJECT_ID('gold.fact_sales', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[fact_sales] (
    [sales_key] bigint NULL,
    [source_sales_key] bigint NULL,
    [order_number] varchar(8000) NULL,
    [customer_key] bigint NULL,
    [customer_entity_key] bigint NULL,
    [product_key] bigint NULL,
    [product_entity_key] bigint NULL,
    [category_key] bigint NULL,
    [location_key] bigint NULL,
    [location_entity_key] bigint NULL,
    [customer_id] int NULL,
    [product_business_key] varchar(8000) NULL,
    [order_date] date NULL,
    [ship_date] date NULL,
    [due_date] date NULL,
    [sales_amount] decimal(18,2) NULL,
    [quantity] int NULL,
    [unit_price] decimal(18,2) NULL,
    [dq_ship_before_order] bit NULL,
    [dq_due_before_order] bit NULL,
    [dq_sales_amount_mismatch] bit NULL,
    [dwh_dq_status] varchar(8000) NULL,
    [dq_order_identity_mismatch] bit NULL,
    [is_sales_eligible] bit NULL,
    [dwh_source_load_ts] datetime2(6) NULL,
    [dwh_silver_load_ts] datetime2(6) NULL,
    [dwh_record_hash] varchar(8000) NULL
  );
END;
GO

IF OBJECT_ID('gold.kpi_audit', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[kpi_audit] (
    [audited_at_utc] datetime2(6) NULL,
    [sales_line_count] bigint NULL,
    [distinct_sales_keys] int NULL,
    [eligible_sales_line_count] bigint NULL,
    [order_identity_mismatch_line_count] bigint NULL,
    [eligible_gross_booked_sales_amount] decimal(38,2) NULL,
    [order_count] bigint NULL,
    [distinct_order_numbers] int NULL,
    [eligible_order_count] bigint NULL,
    [orders_without_lines] bigint NULL,
    [invalid_status_or_date_order_count] bigint NULL,
    [shipping_sla_eligible_order_count] bigint NULL,
    [daily_gross_booked_sales_amount] decimal(38,2) NULL,
    [monthly_gross_booked_sales_amount] decimal(38,2) NULL,
    [lifecycle_eligible_order_count] bigint NULL,
    [payment_eligible_order_count] bigint NULL,
    [shipping_mart_order_count] bigint NULL
  );
END;
GO

IF OBJECT_ID('gold.mart_category_performance', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[mart_category_performance] (
    [category_key] bigint NULL,
    [gross_sales_amount] decimal(38,2) NULL,
    [units_sold] bigint NULL,
    [sales_line_count] bigint NULL
  );
END;
GO

IF OBJECT_ID('gold.mart_customer_order_frequency', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[mart_customer_order_frequency] (
    [customer_entity_key] bigint NULL,
    [order_count] bigint NULL,
    [gross_booked_sales_amount] decimal(38,2) NULL,
    [first_order_date] date NULL,
    [last_order_date] date NULL,
    [is_repeat_customer] bit NULL
  );
END;
GO

IF OBJECT_ID('gold.mart_customer_spend', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[mart_customer_spend] (
    [customer_entity_key] bigint NULL,
    [gross_sales_amount] decimal(38,2) NULL,
    [units_sold] bigint NULL,
    [sales_line_count] bigint NULL,
    [first_sales_date] date NULL,
    [last_sales_date] date NULL
  );
END;
GO

IF OBJECT_ID('gold.mart_daily_sales', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[mart_daily_sales] (
    [order_date] date NULL,
    [gross_sales_amount] decimal(38,2) NULL,
    [units_sold] bigint NULL,
    [sales_line_count] bigint NULL,
    [average_selling_price] decimal(18,4) NULL
  );
END;
GO

IF OBJECT_ID('gold.mart_geography_sales', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[mart_geography_sales] (
    [location_key] bigint NULL,
    [gross_sales_amount] decimal(38,2) NULL,
    [units_sold] bigint NULL,
    [sales_line_count] bigint NULL
  );
END;
GO

IF OBJECT_ID('gold.mart_monthly_sales', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[mart_monthly_sales] (
    [sales_month] date NULL,
    [gross_sales_amount] decimal(38,2) NULL,
    [units_sold] bigint NULL,
    [sales_line_count] bigint NULL,
    [average_selling_price] decimal(18,4) NULL
  );
END;
GO

IF OBJECT_ID('gold.mart_order_lifecycle', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[mart_order_lifecycle] (
    [order_date] date NULL,
    [eligible_order_count] bigint NULL,
    [created_order_count] bigint NULL,
    [packed_order_count] bigint NULL,
    [shipped_order_count] bigint NULL,
    [delivered_order_count] bigint NULL,
    [cancelled_order_count] bigint NULL,
    [returned_order_count] bigint NULL,
    [gross_booked_sales_amount] decimal(38,2) NULL,
    [average_order_value] decimal(18,4) NULL,
    [cancellation_rate_pct] decimal(18,4) NULL,
    [return_rate_pct] decimal(18,4) NULL
  );
END;
GO

IF OBJECT_ID('gold.mart_payment_status', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[mart_payment_status] (
    [order_date] date NULL,
    [payment_status] varchar(8000) NULL,
    [order_count] bigint NULL,
    [gross_booked_sales_amount] decimal(38,2) NULL
  );
END;
GO

IF OBJECT_ID('gold.mart_product_performance', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[mart_product_performance] (
    [product_entity_key] bigint NULL,
    [gross_sales_amount] decimal(38,2) NULL,
    [units_sold] bigint NULL,
    [sales_line_count] bigint NULL
  );
END;
GO

IF OBJECT_ID('gold.mart_sales_yoy', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[mart_sales_yoy] (
    [sales_year] int NULL,
    [gross_sales_amount] decimal(38,2) NULL,
    [prior_year_gross_sales_amount] decimal(38,2) NULL,
    [units_sold] bigint NULL,
    [gross_sales_yoy_pct] decimal(18,4) NULL
  );
END;
GO

IF OBJECT_ID('gold.mart_shipping_sla', 'U') IS NULL
BEGIN
  CREATE TABLE [gold].[mart_shipping_sla] (
    [order_date] date NULL,
    [delivery_zone] varchar(8000) NULL,
    [delivered_order_count] bigint NULL,
    [on_time_order_count] bigint NULL,
    [late_order_count] bigint NULL,
    [on_time_delivery_rate_pct] decimal(18,4) NULL,
    [average_delivery_days] decimal(18,4) NULL
  );
END;
GO
