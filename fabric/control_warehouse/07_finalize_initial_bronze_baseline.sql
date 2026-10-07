-- One-time handoff after the initial PostgreSQL and S3 Bronze loads.
-- This records the already completed baseline and enables future incremental runs.
-- It does not read or modify source systems or Bronze data.

DECLARE @run_id VARCHAR(100) = 'baseline-20260907';
DECLARE @now DATETIME2(3) = SYSUTCDATETIME();

IF NOT EXISTS (SELECT 1 FROM control.ctl_pipeline_run WHERE pipeline_run_id = @run_id)
BEGIN
    INSERT INTO control.ctl_pipeline_run (
        pipeline_run_id, pipeline_name, trigger_type, trigger_name, run_status,
        run_started_ts, run_completed_ts, requested_by, correlation_id,
        objects_requested, objects_succeeded, objects_failed, objects_skipped,
        error_message, dwh_created_ts
    )
    VALUES (
        @run_id, 'pl_bronze_orchestrator', 'manual', 'initial_baseline_handoff',
        'succeeded', @now, @now, 'codex', @run_id,
        10, 10, 0, 0, NULL, @now
    );
END;

DECLARE @baseline TABLE (
    source_object_id INT NOT NULL,
    ingestion_batch_id VARCHAR(128) NOT NULL,
    source_version VARCHAR(500) NULL,
    upper_watermark DATETIME2(3) NULL,
    upper_tie_breaker VARCHAR(200) NULL,
    landing_path VARCHAR(1000) NOT NULL,
    manifest_path VARCHAR(1000) NOT NULL,
    bronze_target_name VARCHAR(256) NOT NULL,
    row_count BIGINT NOT NULL
);

INSERT INTO @baseline VALUES
    (1001, 'pg-1001-baseline-20260907', 'pg-baseline-20260907', NULL, NULL, 'Files/landing/postgresql/customer_master', 'Files/manifests/postgresql/customer_master', 'pg_customer_master', 18484),
    (1002, 'pg-1002-baseline-20260907', 'pg-baseline-20260907', NULL, NULL, 'Files/landing/postgresql/product_master', 'Files/manifests/postgresql/product_master', 'pg_product_master', 397),
    (1003, 'pg-1003-baseline-20260907', 'pg-baseline-20260907', '2026-09-03T06:25:17.204', '15000000', 'Files/landing/postgresql/sales_order_line', 'Files/manifests/postgresql/sales_order_line', 'pg_sales_order_line', 15000000),
    (1004, 'pg-1004-baseline-20260907', 'pg-baseline-20260907', '2026-09-03T06:25:17.204', '746984', 'Files/landing/postgresql/order_status_event', 'Files/manifests/postgresql/order_status_event', 'pg_order_status_event', 746984),
    (1005, 'pg-1005-baseline-20260907', 'pg-baseline-20260907', '2026-09-03T06:25:17.204', '746984', 'Files/landing/postgresql/shipment_status_event', 'Files/manifests/postgresql/shipment_status_event', 'pg_shipment_status_event', 746984),
    (1006, 'pg-1006-baseline-20260907', 'pg-baseline-20260907', '2026-09-03T06:25:17.204', '746984', 'Files/landing/postgresql/payment_status_event', 'Files/manifests/postgresql/payment_status_event', 'pg_payment_status_event', 746984),
    (2001, 's3-2001-baseline-20260907', 's3-baseline-20260907', NULL, NULL, 'Files/landing/s3/location_master', 'Files/manifests/s3/location_master', 's3_location_master', 20007),
    (2002, 's3-2002-baseline-20260907', 's3-baseline-20260907', NULL, NULL, 'Files/landing/s3/delivery_zone_lookup', 'Files/manifests/s3/delivery_zone_lookup', 's3_delivery_zone_lookup', 20007),
    (2003, 's3-2003-baseline-20260907', 's3-baseline-20260907', NULL, NULL, 'Files/landing/s3/warehouse_coverage', 'Files/manifests/s3/warehouse_coverage', 's3_warehouse_coverage', 33636),
    (2004, 's3-2004-baseline-20260907', 's3-baseline-20260907', NULL, NULL, 'Files/landing/s3/geo_hierarchy', 'Files/manifests/s3/geo_hierarchy', 's3_geo_hierarchy', 38);

INSERT INTO control.ctl_bronze_batch (
    ingestion_batch_id, source_object_id, pipeline_run_id, source_version,
    lower_watermark, upper_watermark, lower_tie_breaker, upper_tie_breaker,
    landing_path, manifest_path, bronze_target_name, batch_status,
    rows_landed, rows_committed, committed_ts, error_message,
    dwh_created_ts, dwh_updated_ts
)
SELECT b.ingestion_batch_id, b.source_object_id, @run_id, b.source_version,
       NULL, b.upper_watermark, NULL, b.upper_tie_breaker,
       b.landing_path, b.manifest_path, b.bronze_target_name, 'committed',
       b.row_count, b.row_count, @now, NULL, @now, @now
FROM @baseline b
WHERE NOT EXISTS (
    SELECT 1 FROM control.ctl_bronze_batch x
    WHERE x.ingestion_batch_id = b.ingestion_batch_id
      AND x.source_object_id = b.source_object_id
);

INSERT INTO control.ctl_object_run (
    pipeline_run_id, source_object_id, attempt_number, run_status,
    run_started_ts, run_completed_ts, lower_watermark, upper_watermark,
    lower_tie_breaker, upper_tie_breaker, source_version, rows_read,
    rows_written, rows_rejected, validation_status, error_category,
    error_message, retryable, dwh_created_ts, ingestion_batch_id,
    landing_path, manifest_path, bronze_commit_status, bronze_commit_ts
)
SELECT @run_id, b.source_object_id, 1, 'succeeded', @now, @now,
       NULL, b.upper_watermark, NULL, b.upper_tie_breaker, b.source_version,
       b.row_count, b.row_count, 0, 'passed', NULL, NULL, CAST(0 AS BIT),
       @now, b.ingestion_batch_id, b.landing_path, b.manifest_path,
       'committed', @now
FROM @baseline b
WHERE NOT EXISTS (
    SELECT 1 FROM control.ctl_object_run x
    WHERE x.pipeline_run_id = @run_id
      AND x.source_object_id = b.source_object_id
);

UPDATE s
SET initial_load_completed = CAST(1 AS BIT),
    load_status = 'ready',
    last_successful_watermark = b.upper_watermark,
    last_successful_tie_breaker = b.upper_tie_breaker,
    last_successful_source_version = b.source_version,
    last_successful_run_id = @run_id,
    last_success_ts = @now,
    lock_owner_run_id = NULL,
    lock_acquired_ts = NULL,
    lock_expires_ts = NULL,
    dwh_updated_ts = @now
FROM control.ctl_load_state s
INNER JOIN @baseline b ON b.source_object_id = s.source_object_id;

SELECT source_object_id, ingestion_batch_id, row_count, 'baseline_finalized' AS result
FROM @baseline
ORDER BY source_object_id;
