-- Run after 01_create_enterprise_control_plane.sql and 02_create_control_plane_operations.sql.

SELECT 'source_systems' AS check_name, COUNT(*) AS check_value
FROM control.ctl_source_system
UNION ALL
SELECT 'connections', COUNT(*)
FROM control.ctl_connection
UNION ALL
SELECT 'source_objects', COUNT(*)
FROM control.ctl_source_object
UNION ALL
SELECT 'postgresql_objects', COUNT(*)
FROM control.ctl_source_object WHERE source_system_id = 10
UNION ALL
SELECT 's3_objects', COUNT(*)
FROM control.ctl_source_object WHERE source_system_id = 20
UNION ALL
SELECT 'load_state_rows', COUNT(*)
FROM control.ctl_load_state
UNION ALL
SELECT 'baseline_incremental_watermarks', COUNT(*)
FROM control.ctl_load_state
WHERE last_successful_watermark = CAST('1900-01-01T00:00:00.000' AS DATETIME2(3))
UNION ALL
SELECT 'approved_schema_contracts', COUNT(*)
FROM control.ctl_schema_contract WHERE contract_status = 'approved';
GO

SELECT
    source_object_id,
    source_system_code,
    connection_name,
    source_object_name,
    bronze_target_name,
    load_strategy,
    watermark_column,
    tie_breaker_column,
    initial_load_completed,
    last_successful_watermark,
    load_status,
    drift_action
FROM control.vw_active_source_objects
ORDER BY sequence_order;
GO

SELECT
    source_object_id,
    load_status,
    lock_owner_run_id,
    lock_acquired_ts,
    lock_expires_ts
FROM control.ctl_load_state
WHERE lock_owner_run_id IS NOT NULL
   OR load_status <> 'ready';
GO
