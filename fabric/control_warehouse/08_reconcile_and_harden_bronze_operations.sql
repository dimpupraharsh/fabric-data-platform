-- Reconcile the verified 2026-09-07 incremental proof and harden recurring
-- PostgreSQL watermark ingestion. This script is idempotent and affects only
-- the Fabric control Warehouse; it never changes source or Bronze business data.

IF NOT EXISTS (
    SELECT 1 FROM sys.columns c
    INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_bronze_batch' AND c.name = 'rows_expected'
)
    ALTER TABLE control.ctl_bronze_batch ADD rows_expected BIGINT NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns c
    INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_bronze_batch' AND c.name = 'manifest_written'
)
    ALTER TABLE control.ctl_bronze_batch ADD manifest_written BIT NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns c
    INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = 'control' AND t.name = 'ctl_object_run' AND c.name = 'parent_pipeline_run_id'
)
    ALTER TABLE control.ctl_object_run ADD parent_pipeline_run_id VARCHAR(100) NULL;
GO

-- The four Copy runs below were independently reconciled against source and
-- Bronze on 2026-09-07. Register them before any recurring run is permitted.
IF NOT EXISTS (
    SELECT 1 FROM control.ctl_pipeline_run
    WHERE pipeline_run_id = 'incremental-20260907T163720Z-reconciled'
)
BEGIN
    INSERT INTO control.ctl_pipeline_run (
        pipeline_run_id, pipeline_name, trigger_type, trigger_name, run_status,
        run_started_ts, run_completed_ts, requested_by, correlation_id,
        objects_requested, objects_succeeded, objects_failed, objects_skipped,
        error_message, dwh_created_ts
    ) VALUES (
        'incremental-20260907T163720Z-reconciled', 'pl_bronze_orchestrator',
        'migration', 'reconcile_verified_incremental_proof', 'succeeded',
        CAST('2026-09-07T16:37:20.000' AS DATETIME2(3)),
        CAST('2026-09-07T16:37:20.000' AS DATETIME2(3)),
        'codex', 'incremental-20260907T163720Z', 4, 4, 0, 0, NULL,
        SYSUTCDATETIME()
    );
END;
GO

INSERT INTO control.ctl_bronze_batch (
    ingestion_batch_id, source_object_id, pipeline_run_id, source_version,
    lower_watermark, upper_watermark, lower_tie_breaker, upper_tie_breaker,
    landing_path, manifest_path, bronze_target_name, batch_status,
    rows_landed, rows_committed, committed_ts, error_message,
    dwh_created_ts, dwh_updated_ts, rows_expected, manifest_written
)
SELECT
    v.ingestion_batch_id, v.source_object_id,
    'incremental-20260907T163720Z-reconciled', 'pg-incremental-20260907T163720Z',
    CAST('2026-09-03T06:25:17.204' AS DATETIME2(3)),
    CAST('2026-09-07T16:37:20.000' AS DATETIME2(3)),
    v.lower_tie_breaker, v.upper_tie_breaker,
    o.landing_relative_path,
    CONCAT(o.manifest_relative_path, '/', v.ingestion_batch_id, '.json'),
    o.bronze_target_name, 'committed', v.row_count, v.row_count,
    CAST('2026-09-07T16:37:20.000' AS DATETIME2(3)), NULL,
    SYSUTCDATETIME(), SYSUTCDATETIME(), v.row_count, CAST(0 AS BIT)
FROM (VALUES
    (1003, 'pg-1003-20260907T163720Z-15001001', '15000000', '15001001', CAST(1101 AS BIGINT)),
    (1004, 'pg-1004-20260907T163720Z-747084',   '746984',   '747084',   CAST(100 AS BIGINT)),
    (1005, 'pg-1005-20260907T163720Z-747084',   '746984',   '747084',   CAST(100 AS BIGINT)),
    (1006, 'pg-1006-20260907T163720Z-747084',   '746984',   '747084',   CAST(100 AS BIGINT))
) v(source_object_id, ingestion_batch_id, lower_tie_breaker, upper_tie_breaker, row_count)
INNER JOIN control.ctl_source_object o ON o.source_object_id = v.source_object_id
WHERE NOT EXISTS (
    SELECT 1 FROM control.ctl_bronze_batch b
    WHERE b.source_object_id = v.source_object_id
      AND b.ingestion_batch_id = v.ingestion_batch_id
);
GO

INSERT INTO control.ctl_object_run (
    pipeline_run_id, source_object_id, attempt_number, run_status,
    run_started_ts, run_completed_ts, lower_watermark, upper_watermark,
    lower_tie_breaker, upper_tie_breaker, source_version,
    rows_read, rows_written, rows_rejected, validation_status,
    error_category, error_message, retryable, dwh_created_ts,
    ingestion_batch_id, landing_path, manifest_path, observed_schema_hash,
    bronze_commit_status, bronze_commit_ts, parent_pipeline_run_id
)
SELECT
    'incremental-20260907T163720Z-reconciled', v.source_object_id, 1, 'succeeded',
    CAST('2026-09-07T16:37:20.000' AS DATETIME2(3)),
    CAST('2026-09-07T16:37:20.000' AS DATETIME2(3)),
    CAST('2026-09-03T06:25:17.204' AS DATETIME2(3)),
    CAST('2026-09-07T16:37:20.000' AS DATETIME2(3)),
    v.lower_tie_breaker, v.upper_tie_breaker, 'pg-incremental-20260907T163720Z',
    v.row_count, v.row_count, 0, 'passed', NULL, NULL, CAST(0 AS BIT),
    SYSUTCDATETIME(), v.ingestion_batch_id, o.landing_relative_path,
    CONCAT(o.manifest_relative_path, '/', v.ingestion_batch_id, '.json'),
    NULL, 'committed', CAST('2026-09-07T16:37:20.000' AS DATETIME2(3)), NULL
FROM (VALUES
    (1003, 'pg-1003-20260907T163720Z-15001001', '15000000', '15001001', CAST(1101 AS BIGINT)),
    (1004, 'pg-1004-20260907T163720Z-747084',   '746984',   '747084',   CAST(100 AS BIGINT)),
    (1005, 'pg-1005-20260907T163720Z-747084',   '746984',   '747084',   CAST(100 AS BIGINT)),
    (1006, 'pg-1006-20260907T163720Z-747084',   '746984',   '747084',   CAST(100 AS BIGINT))
) v(source_object_id, ingestion_batch_id, lower_tie_breaker, upper_tie_breaker, row_count)
INNER JOIN control.ctl_source_object o ON o.source_object_id = v.source_object_id
WHERE NOT EXISTS (
    SELECT 1 FROM control.ctl_object_run r
    WHERE r.pipeline_run_id = 'incremental-20260907T163720Z-reconciled'
      AND r.source_object_id = v.source_object_id
);
GO

UPDATE s
SET last_successful_watermark = CAST('2026-09-07T16:37:20.000' AS DATETIME2(3)),
    last_successful_tie_breaker = v.upper_tie_breaker,
    last_successful_source_version = 'pg-incremental-20260907T163720Z',
    last_committed_batch_id = v.ingestion_batch_id,
    last_successful_run_id = 'incremental-20260907T163720Z-reconciled',
    last_success_ts = CAST('2026-09-07T16:37:20.000' AS DATETIME2(3)),
    load_status = 'ready', lock_owner_run_id = NULL,
    lock_acquired_ts = NULL, lock_expires_ts = NULL,
    dwh_updated_ts = SYSUTCDATETIME()
FROM control.ctl_load_state s
INNER JOIN (VALUES
    (1003, '15001001', 'pg-1003-20260907T163720Z-15001001'),
    (1004, '747084',   'pg-1004-20260907T163720Z-747084'),
    (1005, '747084',   'pg-1005-20260907T163720Z-747084'),
    (1006, '747084',   'pg-1006-20260907T163720Z-747084')
) v(source_object_id, upper_tie_breaker, ingestion_batch_id)
    ON v.source_object_id = s.source_object_id
WHERE s.last_successful_watermark < CAST('2026-09-07T16:37:20.000' AS DATETIME2(3))
   OR (s.last_successful_watermark = CAST('2026-09-07T16:37:20.000' AS DATETIME2(3))
       AND TRY_CAST(s.last_successful_tie_breaker AS BIGINT) < TRY_CAST(v.upper_tie_breaker AS BIGINT));
GO

CREATE OR ALTER PROCEDURE control.sp_prepare_bronze_watermark_run
    @pipeline_run_id VARCHAR(100),
    @parent_pipeline_run_id VARCHAR(100) = NULL,
    @source_object_id INT,
    @upper_watermark DATETIME2(3),
    @upper_tie_breaker VARCHAR(200),
    @observed_columns_csv VARCHAR(8000),
    @observed_schema_json VARCHAR(8000)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();
    DECLARE @lower_watermark DATETIME2(3);
    DECLARE @lower_tie_breaker VARCHAR(200);
    DECLARE @expected_columns_csv VARCHAR(8000);
    DECLARE @schema_contract_key BIGINT;
    DECLARE @bronze_target_name VARCHAR(256);
    DECLARE @landing_path VARCHAR(1000);
    DECLARE @manifest_root VARCHAR(1000);
    DECLARE @observed_schema_hash VARCHAR(128);
    DECLARE @ingestion_batch_id VARCHAR(128);
    DECLARE @attempt_number INT;
    DECLARE @lock_acquired INT;
    DECLARE @existing_status VARCHAR(30);

    SELECT
        @lower_watermark = s.last_successful_watermark,
        @lower_tie_breaker = s.last_successful_tie_breaker,
        @bronze_target_name = o.bronze_target_name,
        @landing_path = o.landing_relative_path,
        @manifest_root = o.manifest_relative_path,
        @schema_contract_key = c.schema_contract_key,
        @expected_columns_csv = c.expected_columns_csv
    FROM control.ctl_load_state s
    INNER JOIN control.ctl_source_object o ON o.source_object_id = s.source_object_id
    INNER JOIN control.ctl_schema_contract c ON c.source_object_id = o.source_object_id
        AND c.contract_status = 'approved' AND c.effective_to_ts IS NULL
    WHERE s.source_object_id = @source_object_id
      AND o.load_strategy = 'watermark'
      AND o.is_active = 1;

    IF @bronze_target_name IS NULL
    BEGIN
        RAISERROR('Active watermark source object was not found.', 16, 1);
        RETURN;
    END;

    SET @lower_watermark = COALESCE(@lower_watermark, CAST('1900-01-01' AS DATETIME2(3)));
    SET @lower_tie_breaker = COALESCE(@lower_tie_breaker, '0');
    SET @observed_schema_hash = CONVERT(VARCHAR(128), HASHBYTES('SHA2_256', LOWER(@observed_columns_csv)), 2);
    SET @ingestion_batch_id = CONCAT(
        'pg-', @source_object_id, '-',
        REPLACE(REPLACE(REPLACE(REPLACE(CONVERT(VARCHAR(23), @upper_watermark, 126), '-', ''), ':', ''), 'T', 'T'), '.', ''),
        'Z-', @upper_tie_breaker
    );

    INSERT INTO control.ctl_pipeline_run (
        pipeline_run_id, pipeline_name, trigger_type, trigger_name, run_status,
        run_started_ts, requested_by, correlation_id, objects_requested,
        objects_succeeded, objects_failed, objects_skipped, dwh_created_ts
    )
    SELECT @pipeline_run_id, 'pl_bronze_pg_watermark', 'pipeline',
           'operational_watermark', 'running', @now, 'fabric_pipeline',
           COALESCE(@parent_pipeline_run_id, @pipeline_run_id), 1, 0, 0, 0, @now
    WHERE NOT EXISTS (
        SELECT 1 FROM control.ctl_pipeline_run WHERE pipeline_run_id = @pipeline_run_id
    );

    BEGIN TRANSACTION;

    UPDATE control.ctl_load_state
    SET load_status = 'running', lock_owner_run_id = @pipeline_run_id,
        lock_acquired_ts = @now, lock_expires_ts = DATEADD(MINUTE, 120, @now),
        dwh_updated_ts = @now
    WHERE source_object_id = @source_object_id
      AND (lock_owner_run_id IS NULL OR lock_owner_run_id = @pipeline_run_id OR lock_expires_ts <= @now);

    SET @lock_acquired = @@ROWCOUNT;

    IF @lock_acquired = 0
    BEGIN
        INSERT INTO control.ctl_object_run (
            pipeline_run_id, source_object_id, attempt_number, run_status,
            run_started_ts, run_completed_ts, lower_watermark, upper_watermark,
            lower_tie_breaker, upper_tie_breaker, validation_status,
            error_category, error_message, retryable, dwh_created_ts,
            ingestion_batch_id, bronze_commit_status, parent_pipeline_run_id
        ) VALUES (
            @pipeline_run_id, @source_object_id, 1, 'skipped', @now, @now,
            @lower_watermark, @upper_watermark, @lower_tie_breaker, @upper_tie_breaker,
            'not_run', 'concurrency_lock', 'Another run owns the source-object lease.',
            CAST(1 AS BIT), @now, @ingestion_batch_id, 'not_started', @parent_pipeline_run_id
        );
        UPDATE control.ctl_pipeline_run
        SET run_status = 'skipped', run_completed_ts = @now, objects_skipped = 1
        WHERE pipeline_run_id = @pipeline_run_id;
        COMMIT TRANSACTION;
        SELECT CAST(0 AS BIT) AS can_write, 'lock_not_acquired' AS batch_action;
        RETURN;
    END;

    SELECT @attempt_number = COALESCE(MAX(attempt_number), 0) + 1
    FROM control.ctl_object_run
    WHERE source_object_id = @source_object_id
      AND ingestion_batch_id = @ingestion_batch_id;

    INSERT INTO control.ctl_object_run (
        pipeline_run_id, source_object_id, attempt_number, run_status,
        run_started_ts, lower_watermark, upper_watermark, lower_tie_breaker,
        upper_tie_breaker, source_version, retryable, dwh_created_ts,
        ingestion_batch_id, landing_path, manifest_path, observed_schema_hash,
        bronze_commit_status, parent_pipeline_run_id
    ) VALUES (
        @pipeline_run_id, @source_object_id, @attempt_number, 'running', @now,
        @lower_watermark, @upper_watermark, @lower_tie_breaker, @upper_tie_breaker,
        CONCAT('postgresql:', CONVERT(VARCHAR(23), @upper_watermark, 126), ':', @upper_tie_breaker),
        CAST(1 AS BIT), @now, @ingestion_batch_id,
        CONCAT(@landing_path, '/', @ingestion_batch_id),
        CONCAT(@manifest_root, '/', @ingestion_batch_id, '.json'),
        @observed_schema_hash, 'preflight', @parent_pipeline_run_id
    );

    INSERT INTO control.ctl_schema_observation (
        pipeline_run_id, source_object_id, schema_contract_key,
        observed_schema_hash, observed_schema_json, observed_column_count,
        comparison_result, comparison_detail, observed_ts, dwh_created_ts
    ) VALUES (
        @pipeline_run_id, @source_object_id, @schema_contract_key,
        @observed_schema_hash, @observed_schema_json,
        LEN(@observed_columns_csv) - LEN(REPLACE(@observed_columns_csv, ',', '')) + 1,
        CASE WHEN LOWER(@observed_columns_csv) = LOWER(@expected_columns_csv)
             THEN 'exact_match' ELSE 'breaking_drift' END,
        CASE WHEN LOWER(@observed_columns_csv) = LOWER(@expected_columns_csv)
             THEN 'Observed ordered source columns match the approved contract.'
             ELSE CONCAT('expected=', @expected_columns_csv, '; observed=', @observed_columns_csv) END,
        @now, @now
    );

    IF LOWER(@observed_columns_csv) <> LOWER(@expected_columns_csv)
    BEGIN
        INSERT INTO control.ctl_schema_drift_event (
            schema_observation_key, pipeline_run_id, source_object_id,
            expected_contract_version, expected_schema_hash, observed_schema_hash,
            drift_classification, severity, event_status, action_taken,
            event_detail, opened_ts, dwh_created_ts, dwh_updated_ts
        )
        SELECT MAX(o.schema_observation_key), @pipeline_run_id, @source_object_id,
               c.contract_version, c.expected_schema_hash, @observed_schema_hash,
               'breaking_drift', 'error', 'open', 'blocked_before_copy',
               CONCAT('expected=', @expected_columns_csv, '; observed=', @observed_columns_csv),
               @now, @now, @now
        FROM control.ctl_schema_observation o
        CROSS JOIN control.ctl_schema_contract c
        WHERE o.pipeline_run_id = @pipeline_run_id
          AND o.source_object_id = @source_object_id
          AND c.schema_contract_key = @schema_contract_key
        GROUP BY c.contract_version, c.expected_schema_hash;

        UPDATE control.ctl_object_run
        SET run_status = 'failed', run_completed_ts = @now,
            validation_status = 'failed', error_category = 'schema_drift',
            error_message = 'Breaking source schema drift blocked before Copy.',
            bronze_commit_status = 'blocked'
        WHERE pipeline_run_id = @pipeline_run_id AND source_object_id = @source_object_id
          AND run_status = 'running';
        UPDATE control.ctl_load_state
        SET load_status = 'ready', lock_owner_run_id = NULL,
            lock_acquired_ts = NULL, lock_expires_ts = NULL, dwh_updated_ts = @now
        WHERE source_object_id = @source_object_id AND lock_owner_run_id = @pipeline_run_id;
        UPDATE control.ctl_pipeline_run
        SET run_status = 'failed', run_completed_ts = @now, objects_failed = 1,
            error_message = 'Breaking source schema drift blocked before Copy.'
        WHERE pipeline_run_id = @pipeline_run_id;
        COMMIT TRANSACTION;
        RAISERROR('Breaking source schema drift blocked before Copy.', 16, 1);
        RETURN;
    END;

    IF @upper_watermark < @lower_watermark OR
       (@upper_watermark = @lower_watermark AND TRY_CAST(@upper_tie_breaker AS BIGINT) <= TRY_CAST(@lower_tie_breaker AS BIGINT))
    BEGIN
        UPDATE control.ctl_object_run
        SET run_status = 'skipped', run_completed_ts = @now,
            validation_status = 'passed', error_category = 'no_change',
            error_message = 'No source rows exist after the committed checkpoint.',
            retryable = CAST(0 AS BIT), bronze_commit_status = 'not_required'
        WHERE pipeline_run_id = @pipeline_run_id AND source_object_id = @source_object_id
          AND run_status = 'running';
        UPDATE control.ctl_load_state
        SET load_status = 'ready', lock_owner_run_id = NULL,
            lock_acquired_ts = NULL, lock_expires_ts = NULL, dwh_updated_ts = @now
        WHERE source_object_id = @source_object_id AND lock_owner_run_id = @pipeline_run_id;
        UPDATE control.ctl_pipeline_run
        SET run_status = 'succeeded', run_completed_ts = @now, objects_skipped = 1
        WHERE pipeline_run_id = @pipeline_run_id;
        COMMIT TRANSACTION;
        SELECT CAST(0 AS BIT) AS can_write, 'no_change' AS batch_action,
               @ingestion_batch_id AS ingestion_batch_id;
        RETURN;
    END;

    SELECT @existing_status = batch_status
    FROM control.ctl_bronze_batch
    WHERE ingestion_batch_id = @ingestion_batch_id AND source_object_id = @source_object_id;

    IF @existing_status = 'committed'
    BEGIN
        UPDATE control.ctl_object_run
        SET run_status = 'skipped', run_completed_ts = @now,
            validation_status = 'passed', error_category = 'replay_guard',
            error_message = 'The deterministic batch was already committed.',
            retryable = CAST(0 AS BIT), bronze_commit_status = 'already_committed'
        WHERE pipeline_run_id = @pipeline_run_id AND source_object_id = @source_object_id
          AND run_status = 'running';
        UPDATE control.ctl_load_state
        SET load_status = 'ready', lock_owner_run_id = NULL,
            lock_acquired_ts = NULL, lock_expires_ts = NULL, dwh_updated_ts = @now
        WHERE source_object_id = @source_object_id AND lock_owner_run_id = @pipeline_run_id;
        UPDATE control.ctl_pipeline_run
        SET run_status = 'succeeded', run_completed_ts = @now, objects_skipped = 1
        WHERE pipeline_run_id = @pipeline_run_id;
        COMMIT TRANSACTION;
        SELECT CAST(0 AS BIT) AS can_write, 'already_committed' AS batch_action,
               @ingestion_batch_id AS ingestion_batch_id;
        RETURN;
    END;

    IF @existing_status IS NULL
    BEGIN
        INSERT INTO control.ctl_bronze_batch (
            ingestion_batch_id, source_object_id, pipeline_run_id, source_version,
            lower_watermark, upper_watermark, lower_tie_breaker, upper_tie_breaker,
            landing_path, manifest_path, bronze_target_name, batch_status,
            dwh_created_ts, dwh_updated_ts, manifest_written
        ) VALUES (
            @ingestion_batch_id, @source_object_id, @pipeline_run_id,
            CONCAT('postgresql:', CONVERT(VARCHAR(23), @upper_watermark, 126), ':', @upper_tie_breaker),
            @lower_watermark, @upper_watermark, @lower_tie_breaker, @upper_tie_breaker,
            CONCAT(@landing_path, '/', @ingestion_batch_id),
            CONCAT(@manifest_root, '/', @ingestion_batch_id, '.json'),
            @bronze_target_name, 'staged', @now, @now, CAST(0 AS BIT)
        );
    END
    ELSE
    BEGIN
        UPDATE control.ctl_bronze_batch
        SET pipeline_run_id = @pipeline_run_id, batch_status = 'staged',
            error_message = NULL, dwh_updated_ts = @now
        WHERE ingestion_batch_id = @ingestion_batch_id AND source_object_id = @source_object_id;
    END;

    COMMIT TRANSACTION;

    SELECT CAST(1 AS BIT) AS can_write, 'write_or_resume' AS batch_action,
           @ingestion_batch_id AS ingestion_batch_id,
           CONVERT(VARCHAR(23), @lower_watermark, 126) AS lower_watermark,
           @lower_tie_breaker AS lower_tie_breaker,
           CONVERT(VARCHAR(23), @upper_watermark, 126) AS upper_watermark,
           @upper_tie_breaker AS upper_tie_breaker,
           @bronze_target_name AS bronze_target_name,
           CONCAT(@manifest_root, '/', @ingestion_batch_id, '.json') AS manifest_path;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_set_bronze_expected_rows
    @pipeline_run_id VARCHAR(100),
    @source_object_id INT,
    @ingestion_batch_id VARCHAR(128),
    @rows_expected BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE control.ctl_bronze_batch
    SET rows_expected = @rows_expected, dwh_updated_ts = SYSUTCDATETIME()
    WHERE pipeline_run_id = @pipeline_run_id
      AND source_object_id = @source_object_id
      AND ingestion_batch_id = @ingestion_batch_id
      AND batch_status = 'staged';
    IF @@ROWCOUNT <> 1
        RAISERROR('Expected-row update requires one staged batch owned by this run.', 16, 1);
END;
GO

CREATE OR ALTER PROCEDURE control.sp_commit_bronze_watermark_run
    @pipeline_run_id VARCHAR(100),
    @source_object_id INT,
    @ingestion_batch_id VARCHAR(128),
    @rows_landed BIGINT,
    @manifest_written BIT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();
    DECLARE @rows_expected BIGINT;
    DECLARE @upper_watermark DATETIME2(3);
    DECLARE @upper_tie_breaker VARCHAR(200);
    DECLARE @source_version VARCHAR(500);

    BEGIN TRANSACTION;
    SELECT @rows_expected = rows_expected,
           @upper_watermark = upper_watermark,
           @upper_tie_breaker = upper_tie_breaker,
           @source_version = source_version
    FROM control.ctl_bronze_batch
    WHERE pipeline_run_id = @pipeline_run_id
      AND source_object_id = @source_object_id
      AND ingestion_batch_id = @ingestion_batch_id
      AND batch_status = 'staged';

    IF @rows_expected IS NULL OR @rows_expected <> @rows_landed OR @manifest_written <> 1
    BEGIN
        ROLLBACK TRANSACTION;
        RAISERROR('Commit blocked: source count, Bronze batch count, and manifest must agree.', 16, 1);
        RETURN;
    END;

    IF NOT EXISTS (
        SELECT 1 FROM control.ctl_load_state
        WHERE source_object_id = @source_object_id AND lock_owner_run_id = @pipeline_run_id
    )
    BEGIN
        ROLLBACK TRANSACTION;
        RAISERROR('Commit blocked: this run no longer owns the source-object lease.', 16, 1);
        RETURN;
    END;

    INSERT INTO control.ctl_quality_result (
        pipeline_run_id, source_object_id, ingestion_batch_id, check_name,
        check_scope, severity, threshold_value, observed_value,
        result_status, result_detail, checked_ts, dwh_created_ts
    ) VALUES (
        @pipeline_run_id, @source_object_id, @ingestion_batch_id,
        'source_to_bronze_batch_count', 'batch', 'error',
        CAST(@rows_expected AS DECIMAL(28,6)), CAST(@rows_landed AS DECIMAL(28,6)),
        'passed', 'The bounded source count equals the committed Bronze batch count.',
        @now, @now
    );

    UPDATE control.ctl_bronze_batch
    SET batch_status = 'committed', rows_landed = @rows_landed,
        rows_committed = @rows_landed, manifest_written = @manifest_written,
        committed_ts = @now, error_message = NULL, dwh_updated_ts = @now
    WHERE pipeline_run_id = @pipeline_run_id
      AND source_object_id = @source_object_id
      AND ingestion_batch_id = @ingestion_batch_id
      AND batch_status = 'staged';

    UPDATE control.ctl_object_run
    SET run_status = 'succeeded', run_completed_ts = @now,
        rows_read = @rows_expected, rows_written = @rows_landed, rows_rejected = 0,
        validation_status = 'passed', bronze_commit_status = 'committed',
        bronze_commit_ts = @now, error_category = NULL, error_message = NULL,
        retryable = CAST(0 AS BIT)
    WHERE pipeline_run_id = @pipeline_run_id AND source_object_id = @source_object_id
      AND run_status = 'running';

    UPDATE control.ctl_load_state
    SET load_status = 'ready', initial_load_completed = CAST(1 AS BIT),
        last_successful_watermark = @upper_watermark,
        last_successful_tie_breaker = @upper_tie_breaker,
        last_successful_source_version = @source_version,
        last_committed_batch_id = @ingestion_batch_id,
        last_successful_run_id = @pipeline_run_id, last_success_ts = @now,
        lock_owner_run_id = NULL, lock_acquired_ts = NULL, lock_expires_ts = NULL,
        dwh_updated_ts = @now
    WHERE source_object_id = @source_object_id AND lock_owner_run_id = @pipeline_run_id;

    UPDATE control.ctl_pipeline_run
    SET run_status = 'succeeded', run_completed_ts = @now,
        objects_succeeded = 1, objects_failed = 0, objects_skipped = 0,
        error_message = NULL
    WHERE pipeline_run_id = @pipeline_run_id;

    COMMIT TRANSACTION;
    SELECT CAST(1 AS BIT) AS committed_now, @ingestion_batch_id AS ingestion_batch_id;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_fail_bronze_watermark_run
    @pipeline_run_id VARCHAR(100),
    @source_object_id INT,
    @ingestion_batch_id VARCHAR(128) = NULL,
    @error_category VARCHAR(100),
    @error_message VARCHAR(4000)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();
    UPDATE control.ctl_bronze_batch
    SET batch_status = 'failed', error_message = @error_message, dwh_updated_ts = @now
    WHERE pipeline_run_id = @pipeline_run_id AND source_object_id = @source_object_id
      AND (@ingestion_batch_id IS NULL OR ingestion_batch_id = @ingestion_batch_id)
      AND batch_status <> 'committed';
    UPDATE control.ctl_object_run
    SET run_status = 'failed', run_completed_ts = @now,
        validation_status = 'failed', error_category = @error_category,
        error_message = @error_message, retryable = CAST(1 AS BIT),
        bronze_commit_status = 'failed'
    WHERE pipeline_run_id = @pipeline_run_id AND source_object_id = @source_object_id
      AND run_status = 'running';
    UPDATE control.ctl_load_state
    SET load_status = 'ready', lock_owner_run_id = NULL,
        lock_acquired_ts = NULL, lock_expires_ts = NULL, dwh_updated_ts = @now
    WHERE source_object_id = @source_object_id AND lock_owner_run_id = @pipeline_run_id;
    UPDATE control.ctl_pipeline_run
    SET run_status = 'failed', run_completed_ts = @now,
        objects_failed = 1, error_message = @error_message
    WHERE pipeline_run_id = @pipeline_run_id;
END;
GO

CREATE OR ALTER VIEW control.vw_bronze_operational_readiness
AS
SELECT
    o.source_object_id,
    o.source_object_name,
    o.bronze_target_name,
    o.load_strategy,
    s.load_status,
    s.initial_load_completed,
    s.last_successful_watermark,
    s.last_successful_tie_breaker,
    s.last_committed_batch_id,
    s.last_successful_run_id,
    s.last_success_ts,
    s.lock_owner_run_id,
    CASE
        WHEN o.load_strategy = 'watermark' AND s.last_successful_watermark IS NULL THEN 'checkpoint_missing'
        WHEN s.lock_owner_run_id IS NOT NULL AND s.lock_expires_ts <= SYSUTCDATETIME() THEN 'expired_lock'
        WHEN s.load_status <> 'ready' THEN 'not_ready'
        ELSE 'ready'
    END AS readiness_status
FROM control.ctl_source_object o
INNER JOIN control.ctl_load_state s ON s.source_object_id = o.source_object_id
WHERE o.is_active = 1;
GO

SELECT * FROM control.vw_bronze_operational_readiness ORDER BY source_object_id;
GO
