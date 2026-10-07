-- Register a new complete-population PostgreSQL source without disturbing
-- existing source checkpoints. Keep it inactive until the Bronze target guard
-- and Silver transformation are deployed and tested.
IF NOT EXISTS (SELECT 1 FROM control.ctl_source_object WHERE source_object_id = 1007)
    INSERT INTO control.ctl_source_object (
        source_object_id, source_system_id, connection_id, source_object_name,
        source_object_type, source_locator, source_schema_name, source_table_name,
        bronze_lakehouse_name, bronze_target_name, load_strategy,
        initial_write_behavior, incremental_write_behavior,
        watermark_column, tie_breaker_column, watermark_lookback_seconds,
        load_group, sequence_order, max_parallelism, retry_limit, is_active,
        dwh_created_ts, dwh_updated_ts, landing_relative_path,
        manifest_relative_path, quality_profile_code
    ) VALUES (
        1007, 10, 101, 'retail_oi.order_header', 'table',
        'retail_oi.order_header', 'retail_oi', 'order_header',
        'lh_retail_bronze', 'pg_order_header', 'watermark',
        'append', 'append', 'dwh_load_ts', 'anchor_sales_key', 0,
        'postgresql_order', 65, 1, 3, CAST(0 AS BIT),
        SYSUTCDATETIME(), SYSUTCDATETIME(),
        'Files/landing/postgresql/order_header',
        'Files/manifests/postgresql/order_header', 'transactional_bronze_v1'
    );
GO

IF NOT EXISTS (SELECT 1 FROM control.ctl_load_state WHERE source_object_id = 1007)
    INSERT INTO control.ctl_load_state (
        source_object_id, load_status, initial_load_completed,
        last_successful_watermark, last_successful_tie_breaker,
        dwh_updated_ts
    ) VALUES (
        1007, 'ready', CAST(0 AS BIT),
        CAST('1900-01-01T00:00:00.000' AS DATETIME2(3)), '0',
        SYSUTCDATETIME()
    );
GO

IF NOT EXISTS (
    SELECT 1 FROM control.ctl_schema_contract
    WHERE source_object_id = 1007 AND contract_version = 1
)
    INSERT INTO control.ctl_schema_contract (
        source_object_id, contract_version, contract_status, drift_action,
        expected_columns_csv, expected_schema_hash, effective_from_ts,
        effective_to_ts, approved_by, dwh_created_ts
    ) VALUES (
        1007, 1, 'approved', 'block_on_breaking',
        'order_number,anchor_sales_key,customer_id,order_date,ship_date,due_date,dwh_load_ts,dwh_source_system,order_status,shipment_status,payment_status,delivered_ts,payment_ts,status_updated_ts',
        NULL, SYSUTCDATETIME(), NULL, 'retail_data_engineering', SYSUTCDATETIME()
    );
GO
