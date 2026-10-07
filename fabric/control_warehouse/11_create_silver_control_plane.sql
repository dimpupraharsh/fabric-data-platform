-- Silver transformation metadata, checkpoint, run-audit, and late-dimension re-key support.
-- Run in wh_retail_control after the Bronze control-plane scripts.

IF OBJECT_ID('control.ctl_transform_object', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_transform_object (
        transform_object_id INT NOT NULL,
        transform_name VARCHAR(200) NOT NULL,
        target_lakehouse_name VARCHAR(200) NOT NULL,
        target_schema_name VARCHAR(128) NOT NULL,
        target_table_name VARCHAR(256) NOT NULL,
        notebook_name VARCHAR(200) NOT NULL,
        processing_group VARCHAR(100) NOT NULL,
        sequence_order INT NOT NULL,
        processing_strategy VARCHAR(50) NOT NULL,
        source_object_ids_csv VARCHAR(500) NOT NULL,
        natural_key_columns_csv VARCHAR(1000) NOT NULL,
        is_active BIT NOT NULL,
        dwh_created_ts DATETIME2(3) NOT NULL,
        dwh_updated_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_transform_state', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_transform_state (
        transform_object_id INT NOT NULL,
        transform_status VARCHAR(30) NOT NULL,
        baseline_completed BIT NOT NULL,
        last_processed_bronze_batch_key BIGINT NOT NULL,
        last_successful_run_id VARCHAR(100) NULL,
        last_success_ts DATETIME2(3) NULL,
        lock_owner_run_id VARCHAR(100) NULL,
        lock_acquired_ts DATETIME2(3) NULL,
        lock_expires_ts DATETIME2(3) NULL,
        dwh_updated_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_transform_run', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_transform_run (
        transform_run_key BIGINT IDENTITY NOT NULL,
        pipeline_run_id VARCHAR(100) NOT NULL,
        transform_object_id INT NOT NULL,
        run_status VARCHAR(30) NOT NULL,
        load_mode VARCHAR(30) NOT NULL,
        run_started_ts DATETIME2(3) NOT NULL,
        run_completed_ts DATETIME2(3) NULL,
        lower_bronze_batch_key BIGINT NULL,
        upper_bronze_batch_key BIGINT NULL,
        rows_read BIGINT NULL,
        rows_inserted BIGINT NULL,
        rows_updated BIGINT NULL,
        rows_rejected BIGINT NULL,
        rows_inferred BIGINT NULL,
        rows_rekeyed BIGINT NULL,
        validation_status VARCHAR(30) NULL,
        error_message VARCHAR(4000) NULL,
        dwh_created_ts DATETIME2(3) NOT NULL
    );
END;
GO

IF OBJECT_ID('control.ctl_fact_rekey_queue', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_fact_rekey_queue (
        fact_rekey_queue_key BIGINT IDENTITY NOT NULL,
        pipeline_run_id VARCHAR(100) NOT NULL,
        fact_table_name VARCHAR(256) NOT NULL,
        dimension_name VARCHAR(256) NOT NULL,
        dimension_entity_key VARCHAR(200) NOT NULL,
        affected_from_date DATE NOT NULL,
        affected_to_date DATE NOT NULL,
        queue_status VARCHAR(30) NOT NULL,
        rows_rekeyed BIGINT NULL,
        error_message VARCHAR(4000) NULL,
        queued_ts DATETIME2(3) NOT NULL,
        processed_ts DATETIME2(3) NULL,
        dwh_updated_ts DATETIME2(3) NOT NULL
    );
END;
GO

INSERT INTO control.ctl_transform_object (
    transform_object_id, transform_name, target_lakehouse_name, target_schema_name,
    target_table_name, notebook_name, processing_group, sequence_order,
    processing_strategy, source_object_ids_csv, natural_key_columns_csv,
    is_active, dwh_created_ts, dwh_updated_ts
)
SELECT v.transform_object_id, v.transform_name, 'lh_retail_silver', v.target_schema_name,
       v.target_table_name, v.notebook_name, v.processing_group, v.sequence_order,
       v.processing_strategy, v.source_object_ids_csv, v.natural_key_columns_csv,
       CAST(1 AS BIT), SYSUTCDATETIME(), SYSUTCDATETIME()
FROM (VALUES
    (3001, 'silver_dim_location',              'conformed', 'dim_location',              'nb_silver_dimensions',    'silver_dimensions', 10, 'scd2_rebuild',     '2001,2002,2004', 'country,postal_code'),
    (3002, 'silver_dim_customer',              'conformed', 'dim_customer',              'nb_silver_dimensions',    'silver_dimensions', 20, 'mixed_scd_rebuild','1001,2001',      'customer_id'),
    (3003, 'silver_dim_category',              'conformed', 'dim_category',              'nb_silver_dimensions',    'silver_dimensions', 30, 'scd1_rebuild',     '1002',           'category,subcategory'),
    (3004, 'silver_dim_product',               'conformed', 'dim_product',               'nb_silver_dimensions',    'silver_dimensions', 40, 'scd2_rebuild',     '1002',           'product_business_key'),
    (3005, 'silver_bridge_warehouse_coverage', 'reference', 'bridge_warehouse_coverage', 'nb_silver_dimensions',    'silver_dimensions', 50, 'snapshot_bridge',  '2003',           'warehouse_id,covered_postal_code,delivery_type'),
    (3006, 'silver_fact_sales',                'conformed', 'fact_sales',                'nb_silver_sales',         'silver_facts',      60, 'merge',            '1003',           'source_sales_key'),
    (3007, 'silver_fact_order_event',          'conformed', 'fact_order_event',          'nb_silver_events',        'silver_events',     70, 'append_merge',     '1004',           'source_event_key'),
    (3008, 'silver_fact_shipment_event',       'conformed', 'fact_shipment_event',       'nb_silver_events',        'silver_events',     80, 'append_merge',     '1005',           'source_event_key'),
    (3009, 'silver_fact_payment_event',        'conformed', 'fact_payment_event',        'nb_silver_events',        'silver_events',     90, 'append_merge',     '1006',           'source_event_key'),
    (3010, 'silver_quality_and_reconciliation','quality',   'dq_rejects',                'nb_silver_reconciliation','silver_quality',    100, 'quality',          '1001,1002,1003,1004,1005,1006,2001,2002,2003,2004', 'source_object,source_record_key,rule_code')
) v (
    transform_object_id, transform_name, target_schema_name, target_table_name,
    notebook_name, processing_group, sequence_order, processing_strategy,
    source_object_ids_csv, natural_key_columns_csv
)
WHERE NOT EXISTS (
    SELECT 1 FROM control.ctl_transform_object t
    WHERE t.transform_object_id = v.transform_object_id
);
GO

INSERT INTO control.ctl_transform_state (
    transform_object_id, transform_status, baseline_completed,
    last_processed_bronze_batch_key, last_successful_run_id, last_success_ts,
    lock_owner_run_id, lock_acquired_ts, lock_expires_ts, dwh_updated_ts
)
SELECT t.transform_object_id, 'ready', CAST(0 AS BIT), 0, NULL, NULL,
       NULL, NULL, NULL, SYSUTCDATETIME()
FROM control.ctl_transform_object t
WHERE NOT EXISTS (
    SELECT 1 FROM control.ctl_transform_state s
    WHERE s.transform_object_id = t.transform_object_id
);
GO

CREATE OR ALTER PROCEDURE control.sp_start_transform_run
    @pipeline_run_id VARCHAR(100),
    @transform_object_id INT,
    @load_mode VARCHAR(30),
    @lower_bronze_batch_key BIGINT = NULL,
    @upper_bronze_batch_key BIGINT = NULL,
    @lease_minutes INT = 240
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();

    UPDATE control.ctl_transform_state
    SET transform_status = 'running',
        lock_owner_run_id = @pipeline_run_id,
        lock_acquired_ts = @now,
        lock_expires_ts = DATEADD(MINUTE, @lease_minutes, @now),
        dwh_updated_ts = @now
    WHERE transform_object_id = @transform_object_id
      AND (lock_owner_run_id IS NULL OR lock_owner_run_id = @pipeline_run_id OR lock_expires_ts <= @now);

    IF @@ROWCOUNT <> 1
    BEGIN
        RAISERROR('Silver transform lock could not be acquired.', 16, 1);
        RETURN;
    END;

    INSERT INTO control.ctl_transform_run (
        pipeline_run_id, transform_object_id, run_status, load_mode,
        run_started_ts, run_completed_ts, lower_bronze_batch_key,
        upper_bronze_batch_key, rows_read, rows_inserted, rows_updated,
        rows_rejected, rows_inferred, rows_rekeyed, validation_status,
        error_message, dwh_created_ts
    )
    VALUES (
        @pipeline_run_id, @transform_object_id, 'running', @load_mode,
        @now, NULL, @lower_bronze_batch_key, @upper_bronze_batch_key,
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, @now
    );
END;
GO

CREATE OR ALTER PROCEDURE control.sp_finish_transform_run
    @pipeline_run_id VARCHAR(100),
    @transform_object_id INT,
    @run_status VARCHAR(30),
    @upper_bronze_batch_key BIGINT = NULL,
    @rows_read BIGINT = NULL,
    @rows_inserted BIGINT = NULL,
    @rows_updated BIGINT = NULL,
    @rows_rejected BIGINT = NULL,
    @rows_inferred BIGINT = NULL,
    @rows_rekeyed BIGINT = NULL,
    @validation_status VARCHAR(30) = NULL,
    @error_message VARCHAR(4000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();

    UPDATE control.ctl_transform_run
    SET run_status = @run_status,
        run_completed_ts = @now,
        rows_read = @rows_read,
        rows_inserted = @rows_inserted,
        rows_updated = @rows_updated,
        rows_rejected = @rows_rejected,
        rows_inferred = @rows_inferred,
        rows_rekeyed = @rows_rekeyed,
        validation_status = @validation_status,
        error_message = @error_message
    WHERE pipeline_run_id = @pipeline_run_id
      AND transform_object_id = @transform_object_id
      AND run_status = 'running';

    UPDATE control.ctl_transform_state
    SET transform_status = 'ready',
        baseline_completed = CASE WHEN @run_status = 'succeeded' THEN CAST(1 AS BIT) ELSE baseline_completed END,
        last_processed_bronze_batch_key = CASE
            WHEN @run_status = 'succeeded' THEN COALESCE(@upper_bronze_batch_key, last_processed_bronze_batch_key)
            ELSE last_processed_bronze_batch_key END,
        last_successful_run_id = CASE WHEN @run_status = 'succeeded' THEN @pipeline_run_id ELSE last_successful_run_id END,
        last_success_ts = CASE WHEN @run_status = 'succeeded' THEN @now ELSE last_success_ts END,
        lock_owner_run_id = NULL,
        lock_acquired_ts = NULL,
        lock_expires_ts = NULL,
        dwh_updated_ts = @now
    WHERE transform_object_id = @transform_object_id
      AND lock_owner_run_id = @pipeline_run_id;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_enqueue_fact_rekey
    @pipeline_run_id VARCHAR(100),
    @fact_table_name VARCHAR(256),
    @dimension_name VARCHAR(256),
    @dimension_entity_key VARCHAR(200),
    @affected_from_date DATE,
    @affected_to_date DATE
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO control.ctl_fact_rekey_queue (
        pipeline_run_id, fact_table_name, dimension_name, dimension_entity_key,
        affected_from_date, affected_to_date, queue_status, rows_rekeyed,
        error_message, queued_ts, processed_ts, dwh_updated_ts
    )
    SELECT @pipeline_run_id, @fact_table_name, @dimension_name, @dimension_entity_key,
           @affected_from_date, @affected_to_date, 'pending', NULL,
           NULL, SYSUTCDATETIME(), NULL, SYSUTCDATETIME()
    WHERE NOT EXISTS (
        SELECT 1 FROM control.ctl_fact_rekey_queue
        WHERE fact_table_name = @fact_table_name
          AND dimension_name = @dimension_name
          AND dimension_entity_key = @dimension_entity_key
          AND affected_from_date = @affected_from_date
          AND affected_to_date = @affected_to_date
          AND queue_status IN ('pending', 'running')
    );
END;
GO

CREATE OR ALTER PROCEDURE control.sp_start_silver_run
    @pipeline_run_id VARCHAR(100),
    @load_mode VARCHAR(30)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();

    IF @load_mode NOT IN ('baseline', 'incremental')
    BEGIN
        RAISERROR('load_mode must be baseline or incremental.', 16, 1);
        RETURN;
    END;

    IF EXISTS (SELECT 1 FROM control.ctl_pipeline_run WHERE pipeline_run_id = @pipeline_run_id)
    BEGIN
        RAISERROR('This pipeline run id has already been registered.', 16, 1);
        RETURN;
    END;

    BEGIN TRANSACTION;

    UPDATE s
    SET transform_status = 'running',
        lock_owner_run_id = @pipeline_run_id,
        lock_acquired_ts = @now,
        lock_expires_ts = DATEADD(MINUTE, 360, @now),
        dwh_updated_ts = @now
    FROM control.ctl_transform_state s
    INNER JOIN control.ctl_transform_object t ON t.transform_object_id = s.transform_object_id
    WHERE t.is_active = CAST(1 AS BIT)
      AND (s.lock_owner_run_id IS NULL OR s.lock_expires_ts <= @now);

    IF @@ROWCOUNT <> (SELECT COUNT(*) FROM control.ctl_transform_object WHERE is_active = CAST(1 AS BIT))
    BEGIN
        ROLLBACK TRANSACTION;
        RAISERROR('Could not acquire all Silver transform locks; another run is active.', 16, 1);
        RETURN;
    END;

    INSERT INTO control.ctl_pipeline_run (
        pipeline_run_id, pipeline_name, trigger_type, trigger_name, run_status,
        run_started_ts, requested_by, correlation_id, objects_requested,
        objects_succeeded, objects_failed, objects_skipped, dwh_created_ts
    )
    VALUES (
        @pipeline_run_id, 'pl_silver_orchestrator', 'pipeline', @load_mode, 'running',
        @now, 'fabric_pipeline', @pipeline_run_id,
        (SELECT COUNT(*) FROM control.ctl_transform_object WHERE is_active = CAST(1 AS BIT)),
        0, 0, 0, @now
    );

    INSERT INTO control.ctl_transform_run (
        pipeline_run_id, transform_object_id, run_status, load_mode,
        run_started_ts, lower_bronze_batch_key, upper_bronze_batch_key, dwh_created_ts
    )
    SELECT @pipeline_run_id, t.transform_object_id, 'running', @load_mode,
           @now, s.last_processed_bronze_batch_key,
           (SELECT MAX(bronze_batch_key) FROM control.ctl_bronze_batch WHERE batch_status = 'committed'),
           @now
    FROM control.ctl_transform_object t
    INNER JOIN control.ctl_transform_state s ON s.transform_object_id = t.transform_object_id
    WHERE t.is_active = CAST(1 AS BIT);

    COMMIT TRANSACTION;

    SELECT @pipeline_run_id AS pipeline_run_id,
           (SELECT COUNT(*) FROM control.ctl_transform_object WHERE is_active = CAST(1 AS BIT)) AS transforms_started,
           (SELECT MAX(bronze_batch_key) FROM control.ctl_bronze_batch WHERE batch_status = 'committed') AS latest_bronze_batch_key;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_finish_silver_run
    @pipeline_run_id VARCHAR(100),
    @run_status VARCHAR(30),
    @error_message VARCHAR(4000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();
    DECLARE @upper_batch_key BIGINT = (
        SELECT MAX(bronze_batch_key)
        FROM control.ctl_bronze_batch
        WHERE batch_status = 'committed'
    );

    UPDATE control.ctl_transform_run
    SET run_status = @run_status,
        run_completed_ts = @now,
        upper_bronze_batch_key = COALESCE(@upper_batch_key, upper_bronze_batch_key),
        validation_status = CASE WHEN @run_status = 'succeeded' THEN 'passed' ELSE 'failed' END,
        error_message = @error_message
    WHERE pipeline_run_id = @pipeline_run_id
      AND run_status = 'running';

    UPDATE s
    SET transform_status = 'ready',
        baseline_completed = CASE WHEN @run_status = 'succeeded' THEN CAST(1 AS BIT) ELSE baseline_completed END,
        last_processed_bronze_batch_key = CASE
            WHEN @run_status = 'succeeded' THEN COALESCE(@upper_batch_key, last_processed_bronze_batch_key)
            ELSE last_processed_bronze_batch_key END,
        last_successful_run_id = CASE WHEN @run_status = 'succeeded' THEN @pipeline_run_id ELSE last_successful_run_id END,
        last_success_ts = CASE WHEN @run_status = 'succeeded' THEN @now ELSE last_success_ts END,
        lock_owner_run_id = NULL,
        lock_acquired_ts = NULL,
        lock_expires_ts = NULL,
        dwh_updated_ts = @now
    FROM control.ctl_transform_state s
    INNER JOIN control.ctl_transform_object t ON t.transform_object_id = s.transform_object_id
    WHERE t.is_active = CAST(1 AS BIT)
      AND s.lock_owner_run_id = @pipeline_run_id;

    UPDATE control.ctl_pipeline_run
    SET run_status = @run_status,
        run_completed_ts = @now,
        objects_succeeded = (SELECT COUNT(*) FROM control.ctl_transform_run WHERE pipeline_run_id = @pipeline_run_id AND run_status = 'succeeded'),
        objects_failed = (SELECT COUNT(*) FROM control.ctl_transform_run WHERE pipeline_run_id = @pipeline_run_id AND run_status = 'failed'),
        objects_skipped = 0,
        error_message = @error_message
    WHERE pipeline_run_id = @pipeline_run_id;
END;
GO

CREATE OR ALTER VIEW control.vw_active_silver_transforms
AS
SELECT
    t.transform_object_id,
    t.transform_name,
    t.target_lakehouse_name,
    t.target_schema_name,
    t.target_table_name,
    t.notebook_name,
    t.processing_group,
    t.sequence_order,
    t.processing_strategy,
    t.source_object_ids_csv,
    t.natural_key_columns_csv,
    s.transform_status,
    s.baseline_completed,
    s.last_processed_bronze_batch_key,
    s.last_successful_run_id,
    s.last_success_ts
FROM control.ctl_transform_object t
INNER JOIN control.ctl_transform_state s
    ON s.transform_object_id = t.transform_object_id
WHERE t.is_active = CAST(1 AS BIT);
GO

CREATE OR ALTER VIEW control.vw_silver_operational_readiness
AS
SELECT
    COUNT(*) AS active_transform_count,
    SUM(CASE WHEN s.transform_status = 'ready' THEN 1 ELSE 0 END) AS ready_transform_count,
    SUM(CASE WHEN s.transform_status <> 'ready' THEN 1 ELSE 0 END) AS non_ready_transform_count,
    SUM(CASE WHEN s.baseline_completed = CAST(1 AS BIT) THEN 1 ELSE 0 END) AS baseline_completed_count,
    (SELECT COUNT(*) FROM control.ctl_fact_rekey_queue WHERE queue_status IN ('pending', 'running')) AS open_rekey_count
FROM control.ctl_transform_object t
INNER JOIN control.ctl_transform_state s
    ON s.transform_object_id = t.transform_object_id
WHERE t.is_active = CAST(1 AS BIT);
GO
