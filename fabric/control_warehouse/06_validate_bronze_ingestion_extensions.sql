-- Run after 04_apply_bronze_ingestion_extensions.sql and 05_create_bronze_control_operations.sql.

SELECT 'fabric_connection_ids' AS check_name, COUNT(*) AS check_value
FROM control.ctl_connection
WHERE fabric_connection_id IS NOT NULL
UNION ALL
SELECT 'landing_path_conventions', COUNT(*)
FROM control.ctl_source_object
WHERE landing_relative_path IS NOT NULL AND manifest_relative_path IS NOT NULL
UNION ALL
SELECT 'quality_profiles', COUNT(*)
FROM control.ctl_source_object
WHERE quality_profile_code IS NOT NULL
UNION ALL
SELECT 'object_run_batch_trace_columns', COUNT(*) * 0 + 1
FROM control.ctl_object_run
UNION ALL
SELECT 'bronze_batch_table_queryable', COUNT(*) * 0 + 1
FROM control.ctl_bronze_batch
UNION ALL
SELECT 'schema_observation_table_queryable', COUNT(*) * 0 + 1
FROM control.ctl_schema_observation
UNION ALL
SELECT 'schema_drift_table_queryable', COUNT(*) * 0 + 1
FROM control.ctl_schema_drift_event
UNION ALL
SELECT 'quality_result_table_queryable', COUNT(*) * 0 + 1
FROM control.ctl_quality_result;
GO

SELECT
    connection_id,
    connection_name,
    connection_type,
    fabric_connection_id,
    is_active
FROM control.ctl_connection
ORDER BY connection_id;
GO

SELECT
    source_object_id,
    source_object_name,
    bronze_target_name,
    landing_relative_path,
    manifest_relative_path,
    quality_profile_code,
    load_strategy
FROM control.ctl_source_object
ORDER BY sequence_order;
GO

SELECT TOP 100 *
FROM control.vw_open_operational_alerts
ORDER BY alert_ts DESC;
GO
