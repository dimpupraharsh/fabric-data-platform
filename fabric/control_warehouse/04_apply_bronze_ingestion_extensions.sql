-- Additive migration for the active wh_retail_control enterprise control plane.
-- Run after 01_create_enterprise_control_plane.sql and before 05_create_bronze_control_operations.sql.
-- This migration stores metadata and audit evidence only. It never stores credentials.

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns c
    INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_connection' AND c.name = 'fabric_connection_id'
)
    ALTER TABLE control.ctl_connection ADD fabric_connection_id VARCHAR(100) NULL;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns c
    INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_source_object' AND c.name = 'landing_relative_path'
)
    ALTER TABLE control.ctl_source_object ADD landing_relative_path VARCHAR(1000) NULL;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns c
    INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_source_object' AND c.name = 'manifest_relative_path'
)
    ALTER TABLE control.ctl_source_object ADD manifest_relative_path VARCHAR(1000) NULL;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns c
    INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_source_object' AND c.name = 'quality_profile_code'
)
    ALTER TABLE control.ctl_source_object ADD quality_profile_code VARCHAR(100) NULL;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns c
    INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_schema_contract' AND c.name = 'expected_schema_json'
)
    ALTER TABLE control.ctl_schema_contract ADD expected_schema_json VARCHAR(8000) NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns c INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_load_state' AND c.name = 'last_committed_batch_id'
)
    ALTER TABLE control.ctl_load_state ADD last_committed_batch_id VARCHAR(128) NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns c INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_object_run' AND c.name = 'ingestion_batch_id'
)
    ALTER TABLE control.ctl_object_run ADD ingestion_batch_id VARCHAR(128) NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns c INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_object_run' AND c.name = 'landing_path'
)
    ALTER TABLE control.ctl_object_run ADD landing_path VARCHAR(1000) NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns c INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_object_run' AND c.name = 'manifest_path'
)
    ALTER TABLE control.ctl_object_run ADD manifest_path VARCHAR(1000) NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns c INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_object_run' AND c.name = 'observed_schema_hash'
)
    ALTER TABLE control.ctl_object_run ADD observed_schema_hash VARCHAR(128) NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns c INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_object_run' AND c.name = 'bronze_commit_status'
)
    ALTER TABLE control.ctl_object_run ADD bronze_commit_status VARCHAR(30) NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns c INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_object_run' AND c.name = 'bronze_commit_ts'
)
    ALTER TABLE control.ctl_object_run ADD bronze_commit_ts DATETIME2(3) NULL;
GO

IF OBJECT_ID('control.ctl_bronze_batch', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_bronze_batch (
        bronze_batch_key BIGINT IDENTITY NOT NULL,
        ingestion_batch_id VARCHAR(128) NOT NULL,
        source_object_id INT NOT NULL,
        pipeline_run_id VARCHAR(100) NOT NULL,
        source_version VARCHAR(500) NULL,
        lower_watermark DATETIME2(3) NULL,
        upper_watermark DATETIME2(3) NULL,
        lower_tie_breaker VARCHAR(200) NULL,
        upper_tie_breaker VARCHAR(200) NULL,
        landing_path VARCHAR(1000) NOT NULL,
        manifest_path VARCHAR(1000) NOT NULL,
        bronze_target_name VARCHAR(256) NOT NULL,
        batch_status VARCHAR(30) NOT NULL,
        rows_landed BIGINT NULL,
        rows_committed BIGINT NULL,
        committed_ts DATETIME2(3) NULL,
        error_message VARCHAR(4000) NULL,
        dwh_created_ts DATETIME2(3) NOT NULL,
        dwh_updated_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_schema_observation', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_schema_observation (
        schema_observation_key BIGINT IDENTITY NOT NULL,
        pipeline_run_id VARCHAR(100) NOT NULL,
        source_object_id INT NOT NULL,
        schema_contract_key BIGINT NULL,
        observed_schema_hash VARCHAR(128) NOT NULL,
        observed_schema_json VARCHAR(8000) NOT NULL,
        observed_column_count INT NOT NULL,
        comparison_result VARCHAR(30) NOT NULL,
        comparison_detail VARCHAR(4000) NULL,
        observed_ts DATETIME2(3) NOT NULL,
        dwh_created_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_schema_drift_event', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_schema_drift_event (
        schema_drift_event_key BIGINT IDENTITY NOT NULL,
        schema_observation_key BIGINT NOT NULL,
        pipeline_run_id VARCHAR(100) NOT NULL,
        source_object_id INT NOT NULL,
        expected_contract_version INT NULL,
        expected_schema_hash VARCHAR(128) NULL,
        observed_schema_hash VARCHAR(128) NOT NULL,
        drift_classification VARCHAR(50) NOT NULL,
        severity VARCHAR(30) NOT NULL,
        event_status VARCHAR(30) NOT NULL,
        action_taken VARCHAR(100) NOT NULL,
        event_detail VARCHAR(4000) NULL,
        opened_ts DATETIME2(3) NOT NULL,
        resolved_ts DATETIME2(3) NULL,
        resolved_by VARCHAR(200) NULL,
        resolution_note VARCHAR(4000) NULL,
        dwh_created_ts DATETIME2(3) NOT NULL,
        dwh_updated_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_quality_result', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_quality_result (
        quality_result_key BIGINT IDENTITY NOT NULL,
        pipeline_run_id VARCHAR(100) NOT NULL,
        source_object_id INT NOT NULL,
        ingestion_batch_id VARCHAR(128) NULL,
        check_name VARCHAR(200) NOT NULL,
        check_scope VARCHAR(50) NOT NULL,
        severity VARCHAR(30) NOT NULL,
        threshold_value DECIMAL(28,6) NULL,
        observed_value DECIMAL(28,6) NULL,
        result_status VARCHAR(30) NOT NULL,
        result_detail VARCHAR(4000) NULL,
        checked_ts DATETIME2(3) NOT NULL,
        dwh_created_ts DATETIME2(3) NOT NULL
    );
END;
GO

-- Store Fabric IDs as the executable identity and display names as human-readable metadata.
UPDATE control.ctl_connection
SET connection_name = 'conn_postgresql_salefisher_gateway',
    connection_type = 'on_premises_gateway',
    fabric_connection_id = 'e3607aae-ab0a-4954-968c-613ebd192eeb',
    dwh_updated_ts = SYSUTCDATETIME()
WHERE connection_id = 101;
GO

UPDATE control.ctl_connection
SET connection_name = 'Amazon s3 connection dimpu',
    connection_type = 'shareable_cloud',
    fabric_connection_id = '2977a806-dd08-4233-b4d1-bd1521ec0d16',
    dwh_updated_ts = SYSUTCDATETIME()
WHERE connection_id = 201;
GO

-- Define deterministic Bronze landing and manifest roots. Pipelines append the batch identifier.
UPDATE control.ctl_source_object
SET landing_relative_path = CASE source_object_id
    WHEN 1001 THEN 'Files/landing/postgresql/customer_master'
    WHEN 1002 THEN 'Files/landing/postgresql/product_master'
    WHEN 1003 THEN 'Files/landing/postgresql/sales_order_line'
    WHEN 1004 THEN 'Files/landing/postgresql/order_status_event'
    WHEN 1005 THEN 'Files/landing/postgresql/shipment_status_event'
    WHEN 1006 THEN 'Files/landing/postgresql/payment_status_event'
    WHEN 2001 THEN 'Files/landing/s3/location_master'
    WHEN 2002 THEN 'Files/landing/s3/delivery_zone_lookup'
    WHEN 2003 THEN 'Files/landing/s3/warehouse_coverage'
    WHEN 2004 THEN 'Files/landing/s3/geo_hierarchy'
END,
manifest_relative_path = CASE source_object_id
    WHEN 1001 THEN 'Files/manifests/postgresql/customer_master'
    WHEN 1002 THEN 'Files/manifests/postgresql/product_master'
    WHEN 1003 THEN 'Files/manifests/postgresql/sales_order_line'
    WHEN 1004 THEN 'Files/manifests/postgresql/order_status_event'
    WHEN 1005 THEN 'Files/manifests/postgresql/shipment_status_event'
    WHEN 1006 THEN 'Files/manifests/postgresql/payment_status_event'
    WHEN 2001 THEN 'Files/manifests/s3/location_master'
    WHEN 2002 THEN 'Files/manifests/s3/delivery_zone_lookup'
    WHEN 2003 THEN 'Files/manifests/s3/warehouse_coverage'
    WHEN 2004 THEN 'Files/manifests/s3/geo_hierarchy'
END,
quality_profile_code = CASE
    WHEN source_system_id = 10 THEN 'transactional_bronze_v1'
    WHEN source_system_id = 20 THEN 'reference_snapshot_bronze_v1'
END,
dwh_updated_ts = SYSUTCDATETIME()
WHERE source_object_id IN (1001,1002,1003,1004,1005,1006,2001,2002,2003,2004);
GO

-- The current PostgreSQL customer source includes these geography columns.
-- Correct the initial contract before schema-drift enforcement begins.
UPDATE control.ctl_schema_contract
SET expected_columns_csv = 'customer_key,customer_id,customer_business_key,first_name,last_name,marital_status,gender,create_date,birth_date,country,state_province,city,postal_code,dwh_load_ts,dwh_source_system',
    drift_action = 'block_on_breaking'
WHERE source_object_id = 1001
  AND contract_version = 1
  AND effective_to_ts IS NULL;
GO

UPDATE control.ctl_schema_contract
SET drift_action = 'block_on_breaking'
WHERE source_object_id IN (1002,1003,1004,1005,1006,2001,2002,2003,2004)
  AND contract_version = 1
  AND effective_to_ts IS NULL;
GO
