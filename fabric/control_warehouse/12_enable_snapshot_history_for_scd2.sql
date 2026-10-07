/*
Purpose: retain successive PostgreSQL master and S3 reference snapshots in
Bronze so Silver can observe attribute changes over time and build SCD2.

This changes control metadata only. It does not read or modify source data,
Bronze rows, watermarks, or existing manifests. Baseline tables already loaded
remain as-is; the snapshot child adds lineage columns before the next append.
*/

UPDATE control.ctl_source_object
SET load_strategy = 'snapshot_append',
    initial_write_behavior = 'append',
    incremental_write_behavior = 'append',
    dwh_updated_ts = SYSUTCDATETIME()
WHERE source_object_id IN (1001, 1002, 2001, 2002, 2003, 2004);
GO

SELECT source_object_id, source_object_name, load_strategy,
       initial_write_behavior, incremental_write_behavior, bronze_target_name
FROM control.ctl_source_object
WHERE source_object_id IN (1001, 1002, 2001, 2002, 2003, 2004)
ORDER BY source_object_id;
GO
