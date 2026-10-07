-- Run in wh_retail_control after 00_retire_legacy_control_models.sql.
-- This control plane contains metadata and operational audit data only.
-- Never store passwords, access keys, or connection strings in these tables.

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'control')
BEGIN
    EXEC('CREATE SCHEMA control');
END;
GO

IF OBJECT_ID('control.ctl_source_system', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_source_system (
        source_system_id INT NOT NULL,
        source_system_code VARCHAR(100) NOT NULL,
        source_system_name VARCHAR(200) NOT NULL,
        source_engine VARCHAR(100) NOT NULL,
        source_role VARCHAR(50) NOT NULL,
        data_owner VARCHAR(200) NULL,
        data_classification VARCHAR(50) NOT NULL,
        is_active BIT NOT NULL,
        dwh_created_ts DATETIME2(3) NOT NULL,
        dwh_updated_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_connection', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_connection (
        connection_id INT NOT NULL,
        source_system_id INT NOT NULL,
        connection_name VARCHAR(200) NOT NULL,
        connection_type VARCHAR(100) NOT NULL,
        gateway_name VARCHAR(200) NULL,
        environment_name VARCHAR(50) NOT NULL,
        authentication_mode VARCHAR(100) NULL,
        connection_owner VARCHAR(200) NULL,
        is_active BIT NOT NULL,
        dwh_created_ts DATETIME2(3) NOT NULL,
        dwh_updated_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_source_object', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_source_object (
        source_object_id INT NOT NULL,
        source_system_id INT NOT NULL,
        connection_id INT NOT NULL,
        source_object_name VARCHAR(500) NOT NULL,
        source_object_type VARCHAR(50) NOT NULL,
        source_locator VARCHAR(1000) NOT NULL,
        source_schema_name VARCHAR(128) NULL,
        source_table_name VARCHAR(256) NULL,
        bronze_lakehouse_name VARCHAR(200) NOT NULL,
        bronze_target_name VARCHAR(256) NOT NULL,
        load_strategy VARCHAR(50) NOT NULL,
        initial_write_behavior VARCHAR(50) NOT NULL,
        incremental_write_behavior VARCHAR(50) NULL,
        watermark_column VARCHAR(128) NULL,
        tie_breaker_column VARCHAR(128) NULL,
        watermark_lookback_seconds INT NOT NULL,
        load_group VARCHAR(100) NOT NULL,
        sequence_order INT NOT NULL,
        max_parallelism INT NOT NULL,
        retry_limit INT NOT NULL,
        is_active BIT NOT NULL,
        dwh_created_ts DATETIME2(3) NOT NULL,
        dwh_updated_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_load_state', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_load_state (
        source_object_id INT NOT NULL,
        load_status VARCHAR(30) NOT NULL,
        initial_load_completed BIT NOT NULL,
        last_successful_watermark DATETIME2(3) NULL,
        last_successful_tie_breaker VARCHAR(200) NULL,
        last_successful_source_version VARCHAR(500) NULL,
        last_successful_run_id VARCHAR(100) NULL,
        last_success_ts DATETIME2(3) NULL,
        lock_owner_run_id VARCHAR(100) NULL,
        lock_acquired_ts DATETIME2(3) NULL,
        lock_expires_ts DATETIME2(3) NULL,
        dwh_updated_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_pipeline_run', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_pipeline_run (
        pipeline_run_id VARCHAR(100) NOT NULL,
        pipeline_name VARCHAR(200) NOT NULL,
        trigger_type VARCHAR(50) NOT NULL,
        trigger_name VARCHAR(200) NULL,
        run_status VARCHAR(30) NOT NULL,
        run_started_ts DATETIME2(3) NOT NULL,
        run_completed_ts DATETIME2(3) NULL,
        requested_by VARCHAR(200) NULL,
        correlation_id VARCHAR(100) NULL,
        objects_requested INT NOT NULL,
        objects_succeeded INT NOT NULL,
        objects_failed INT NOT NULL,
        objects_skipped INT NOT NULL,
        error_message VARCHAR(4000) NULL,
        dwh_created_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_object_run', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_object_run (
        object_run_key BIGINT IDENTITY NOT NULL,
        pipeline_run_id VARCHAR(100) NOT NULL,
        source_object_id INT NOT NULL,
        attempt_number INT NOT NULL,
        run_status VARCHAR(30) NOT NULL,
        run_started_ts DATETIME2(3) NOT NULL,
        run_completed_ts DATETIME2(3) NULL,
        lower_watermark DATETIME2(3) NULL,
        upper_watermark DATETIME2(3) NULL,
        lower_tie_breaker VARCHAR(200) NULL,
        upper_tie_breaker VARCHAR(200) NULL,
        source_version VARCHAR(500) NULL,
        rows_read BIGINT NULL,
        rows_written BIGINT NULL,
        rows_rejected BIGINT NULL,
        validation_status VARCHAR(30) NULL,
        error_category VARCHAR(100) NULL,
        error_message VARCHAR(4000) NULL,
        retryable BIT NULL,
        dwh_created_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_schema_contract', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_schema_contract (
        schema_contract_key BIGINT IDENTITY NOT NULL,
        source_object_id INT NOT NULL,
        contract_version INT NOT NULL,
        contract_status VARCHAR(30) NOT NULL,
        drift_action VARCHAR(50) NOT NULL,
        expected_columns_csv VARCHAR(4000) NOT NULL,
        expected_schema_hash VARCHAR(128) NULL,
        effective_from_ts DATETIME2(3) NOT NULL,
        effective_to_ts DATETIME2(3) NULL,
        approved_by VARCHAR(200) NULL,
        dwh_created_ts DATETIME2(3) NOT NULL
    );
END;
GO

INSERT INTO control.ctl_source_system (
    source_system_id, source_system_code, source_system_name, source_engine,
    source_role, data_owner, data_classification, is_active, dwh_created_ts, dwh_updated_ts
)
SELECT 10, 'postgresql_salefisher', 'Salefisher transactional source', 'postgresql',
       'transactional', 'retail_data_engineering', 'internal', CAST(1 AS BIT), SYSUTCDATETIME(), SYSUTCDATETIME()
WHERE NOT EXISTS (SELECT 1 FROM control.ctl_source_system WHERE source_system_id = 10);
GO

INSERT INTO control.ctl_source_system (
    source_system_id, source_system_code, source_system_name, source_engine,
    source_role, data_owner, data_classification, is_active, dwh_created_ts, dwh_updated_ts
)
SELECT 20, 'aws_s3_retail_ref', 'AWS S3 geography and fulfillment reference source', 'amazon_s3',
       'reference', 'retail_data_engineering', 'internal', CAST(1 AS BIT), SYSUTCDATETIME(), SYSUTCDATETIME()
WHERE NOT EXISTS (SELECT 1 FROM control.ctl_source_system WHERE source_system_id = 20);
GO

INSERT INTO control.ctl_connection (
    connection_id, source_system_id, connection_name, connection_type, gateway_name,
    environment_name, authentication_mode, connection_owner, is_active, dwh_created_ts, dwh_updated_ts
)
SELECT 101, 10, 'conn_postgresql_salefisher_gateway', 'on_premises_gateway', NULL,
       'dev', 'postgresql_credentials', 'retail_data_engineering', CAST(1 AS BIT), SYSUTCDATETIME(), SYSUTCDATETIME()
WHERE NOT EXISTS (SELECT 1 FROM control.ctl_connection WHERE connection_id = 101);
GO

INSERT INTO control.ctl_connection (
    connection_id, source_system_id, connection_name, connection_type, gateway_name,
    environment_name, authentication_mode, connection_owner, is_active, dwh_created_ts, dwh_updated_ts
)
SELECT 201, 20, 'shortcut_retail_ref', 'onelake_shortcut', NULL,
       'dev', 'aws_iam', 'retail_data_engineering', CAST(1 AS BIT), SYSUTCDATETIME(), SYSUTCDATETIME()
WHERE NOT EXISTS (SELECT 1 FROM control.ctl_connection WHERE connection_id = 201);
GO

INSERT INTO control.ctl_source_object (
    source_object_id, source_system_id, connection_id, source_object_name, source_object_type,
    source_locator, source_schema_name, source_table_name, bronze_lakehouse_name,
    bronze_target_name, load_strategy, initial_write_behavior, incremental_write_behavior,
    watermark_column, tie_breaker_column, watermark_lookback_seconds, load_group,
    sequence_order, max_parallelism, retry_limit, is_active, dwh_created_ts, dwh_updated_ts
)
SELECT v.source_object_id, v.source_system_id, v.connection_id, v.source_object_name, v.source_object_type,
       v.source_locator, v.source_schema_name, v.source_table_name, v.bronze_lakehouse_name,
       v.bronze_target_name, v.load_strategy, v.initial_write_behavior, v.incremental_write_behavior,
       v.watermark_column, v.tie_breaker_column, v.watermark_lookback_seconds, v.load_group,
       v.sequence_order, v.max_parallelism, v.retry_limit, v.is_active, SYSUTCDATETIME(), SYSUTCDATETIME()
FROM (VALUES
    (1001, 10, 101, 'retail_oi.customer_master',       'table', 'retail_oi.customer_master',       'retail_oi', 'customer_master',       'lh_retail_bronze', 'pg_customer_master',       'full_refresh',              'overwrite', NULL,     NULL,          NULL,        0, 'postgresql_master', 10, 1, 2, CAST(1 AS BIT)),
    (1002, 10, 101, 'retail_oi.product_master',        'table', 'retail_oi.product_master',        'retail_oi', 'product_master',        'lh_retail_bronze', 'pg_product_master',        'full_refresh',              'overwrite', NULL,     NULL,          NULL,        0, 'postgresql_master', 20, 1, 2, CAST(1 AS BIT)),
    (1003, 10, 101, 'retail_oi.sales_order_line',      'table', 'retail_oi.sales_order_line',      'retail_oi', 'sales_order_line',      'lh_retail_bronze', 'pg_sales_order_line',      'watermark',                 'overwrite', 'append', 'dwh_load_ts', 'sales_key',   0, 'postgresql_fact',   30, 1, 3, CAST(1 AS BIT)),
    (1004, 10, 101, 'retail_oi.order_status_event',    'table', 'retail_oi.order_status_event',    'retail_oi', 'order_status_event',    'lh_retail_bronze', 'pg_order_status_event',    'watermark',                 'overwrite', 'append', 'dwh_load_ts', 'event_key',   0, 'postgresql_event',  40, 1, 3, CAST(1 AS BIT)),
    (1005, 10, 101, 'retail_oi.shipment_status_event', 'table', 'retail_oi.shipment_status_event', 'retail_oi', 'shipment_status_event', 'lh_retail_bronze', 'pg_shipment_status_event', 'watermark',                 'overwrite', 'append', 'dwh_load_ts', 'event_key',   0, 'postgresql_event',  50, 1, 3, CAST(1 AS BIT)),
    (1006, 10, 101, 'retail_oi.payment_status_event',  'table', 'retail_oi.payment_status_event',  'retail_oi', 'payment_status_event',  'lh_retail_bronze', 'pg_payment_status_event',  'watermark',                 'overwrite', 'append', 'dwh_load_ts', 'event_key',   0, 'postgresql_event',  60, 1, 3, CAST(1 AS BIT)),
    (2001, 20, 201, 's3.location_master',              'file',  's3://fabric-datawarehouse-project/retail_ref/location_master/location_master.csv',             NULL, NULL, 'lh_retail_bronze', 's3_location_master',       'full_snapshot',             'overwrite', NULL,     NULL,          NULL,        0, 's3_reference',      70, 1, 2, CAST(1 AS BIT)),
    (2002, 20, 201, 's3.delivery_zone_lookup',         'file',  's3://fabric-datawarehouse-project/retail_ref/delivery_zone_lookup/delivery_zone_lookup.csv', NULL, NULL, 'lh_retail_bronze', 's3_delivery_zone_lookup', 'full_snapshot',             'overwrite', NULL,     NULL,          NULL,        0, 's3_reference',      80, 1, 2, CAST(1 AS BIT)),
    (2003, 20, 201, 's3.warehouse_coverage',           'file',  's3://fabric-datawarehouse-project/retail_ref/warehouse_coverage/warehouse_coverage.csv',     NULL, NULL, 'lh_retail_bronze', 's3_warehouse_coverage',   'full_snapshot',             'overwrite', NULL,     NULL,          NULL,        0, 's3_reference',      90, 1, 2, CAST(1 AS BIT)),
    (2004, 20, 201, 's3.geo_hierarchy',                'file',  's3://fabric-datawarehouse-project/retail_ref/geo_hierarchy/geo_hierarchy.csv',                 NULL, NULL, 'lh_retail_bronze', 's3_geo_hierarchy',         'full_snapshot',             'overwrite', NULL,     NULL,          NULL,        0, 's3_reference',      100, 1, 2, CAST(1 AS BIT))
) v (
    source_object_id, source_system_id, connection_id, source_object_name, source_object_type,
    source_locator, source_schema_name, source_table_name, bronze_lakehouse_name,
    bronze_target_name, load_strategy, initial_write_behavior, incremental_write_behavior,
    watermark_column, tie_breaker_column, watermark_lookback_seconds, load_group,
    sequence_order, max_parallelism, retry_limit, is_active
)
WHERE NOT EXISTS (
    SELECT 1 FROM control.ctl_source_object o WHERE o.source_object_id = v.source_object_id
);
GO

INSERT INTO control.ctl_load_state (
    source_object_id, load_status, initial_load_completed, last_successful_watermark,
    last_successful_tie_breaker, last_successful_source_version, last_successful_run_id,
    last_success_ts, lock_owner_run_id, lock_acquired_ts, lock_expires_ts, dwh_updated_ts
)
SELECT
    o.source_object_id,
    'ready',
    CAST(0 AS BIT),
    CASE WHEN o.load_strategy = 'watermark'
         THEN CAST('1900-01-01T00:00:00.000' AS DATETIME2(3)) END,
    CASE WHEN o.load_strategy = 'watermark' THEN '0' END,
    NULL, NULL, NULL, NULL, NULL, NULL, SYSUTCDATETIME()
FROM control.ctl_source_object o
WHERE NOT EXISTS (
    SELECT 1 FROM control.ctl_load_state s WHERE s.source_object_id = o.source_object_id
);
GO

INSERT INTO control.ctl_schema_contract (
    source_object_id, contract_version, contract_status, drift_action, expected_columns_csv,
    expected_schema_hash, effective_from_ts, effective_to_ts, approved_by, dwh_created_ts
)
SELECT v.source_object_id, 1, 'approved', 'log_and_continue', v.expected_columns_csv,
       NULL, SYSUTCDATETIME(), NULL, 'retail_data_engineering', SYSUTCDATETIME()
FROM (VALUES
    (1001, 'customer_key,customer_id,customer_business_key,first_name,last_name,marital_status,gender,create_date,birth_date,country,dwh_load_ts,dwh_source_system'),
    (1002, 'product_key,product_id,product_business_key,product_name,product_cost,product_line,start_date,end_date,category,subcategory,maintenance_flag,dwh_load_ts,dwh_source_system'),
    (1003, 'sales_key,order_number,product_business_key,customer_id,order_date,ship_date,due_date,sales_amount,quantity,unit_price,dwh_load_ts,dwh_source_system'),
    (1004, 'event_key,order_number,event_status,event_ts,dwh_load_ts,dwh_source_system'),
    (1005, 'event_key,order_number,shipment_status,event_ts,dwh_load_ts,dwh_source_system'),
    (1006, 'event_key,order_number,payment_status,event_ts,dwh_load_ts,dwh_source_system'),
    (2001, 'location_id,country,region,subregion,state_province,city,postal_code,timezone,market_area,is_active,effective_from,effective_to'),
    (2002, 'postal_code,delivery_zone,zone_priority,standard_sla_days,express_sla_days,remote_area_flag,serviceability_flag,last_updated_date'),
    (2003, 'warehouse_id,warehouse_name,warehouse_country,service_region,covered_country,covered_region,covered_postal_code,delivery_type,serviceability_flag,max_sla_days,last_updated_date'),
    (2004, 'country,country_code,region,region_code,subregion,market,sales_territory,active_flag,last_updated_date')
) v (source_object_id, expected_columns_csv)
WHERE NOT EXISTS (
    SELECT 1
    FROM control.ctl_schema_contract c
    WHERE c.source_object_id = v.source_object_id
      AND c.contract_version = 1
);
GO
