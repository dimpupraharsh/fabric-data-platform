-- Register the order-grain Silver transform after the notebook and pipeline
-- are deployed. Inactive until a successful Bronze order_header baseline.
IF NOT EXISTS (SELECT 1 FROM control.ctl_transform_object WHERE transform_object_id = 3011)
    INSERT INTO control.ctl_transform_object (
        transform_object_id, transform_name, target_lakehouse_name,
        target_schema_name, target_table_name, notebook_name,
        processing_group, sequence_order, processing_strategy,
        source_object_ids_csv, natural_key_columns_csv,
        is_active, dwh_created_ts, dwh_updated_ts
    ) VALUES (
        3011, 'silver_fact_order', 'lh_retail_silver',
        'conformed', 'fact_order', 'nb_silver_order_header',
        'silver_facts', 95, 'merge', '1007', 'order_number',
        CAST(0 AS BIT), SYSUTCDATETIME(), SYSUTCDATETIME()
    );
GO

IF NOT EXISTS (SELECT 1 FROM control.ctl_transform_state WHERE transform_object_id = 3011)
    INSERT INTO control.ctl_transform_state (
        transform_object_id, transform_status, baseline_completed,
        last_processed_bronze_batch_key, dwh_updated_ts
    ) VALUES (3011, 'ready', CAST(0 AS BIT), 0, SYSUTCDATETIME());
GO
