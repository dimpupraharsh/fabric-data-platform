-- Bronze idempotency, schema-observation, schema-drift, and quality operations.
-- Run after 04_apply_bronze_ingestion_extensions.sql.

CREATE OR ALTER PROCEDURE control.sp_start_bronze_batch
    @pipeline_run_id VARCHAR(100),
    @source_object_id INT,
    @ingestion_batch_id VARCHAR(128),
    @source_version VARCHAR(500) = NULL,
    @lower_watermark DATETIME2(3) = NULL,
    @upper_watermark DATETIME2(3) = NULL,
    @lower_tie_breaker VARCHAR(200) = NULL,
    @upper_tie_breaker VARCHAR(200) = NULL,
    @landing_path VARCHAR(1000),
    @manifest_path VARCHAR(1000),
    @bronze_target_name VARCHAR(256)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();
    DECLARE @existing_status VARCHAR(30);

    SELECT @existing_status = batch_status
    FROM control.ctl_bronze_batch
    WHERE ingestion_batch_id = @ingestion_batch_id
      AND source_object_id = @source_object_id;

    IF @existing_status = 'committed'
    BEGIN
        SELECT CAST(0 AS BIT) AS can_write, 'already_committed' AS batch_action;
        RETURN;
    END;

    IF @existing_status IS NULL
    BEGIN
        INSERT INTO control.ctl_bronze_batch (
            ingestion_batch_id, source_object_id, pipeline_run_id, source_version,
            lower_watermark, upper_watermark, lower_tie_breaker, upper_tie_breaker,
            landing_path, manifest_path, bronze_target_name, batch_status,
            rows_landed, rows_committed, committed_ts, error_message,
            dwh_created_ts, dwh_updated_ts
        )
        VALUES (
            @ingestion_batch_id, @source_object_id, @pipeline_run_id, @source_version,
            @lower_watermark, @upper_watermark, @lower_tie_breaker, @upper_tie_breaker,
            @landing_path, @manifest_path, @bronze_target_name, 'staged',
            NULL, NULL, NULL, NULL, @now, @now
        );
    END
    ELSE
    BEGIN
        UPDATE control.ctl_bronze_batch
        SET pipeline_run_id = @pipeline_run_id,
            batch_status = 'staged',
            error_message = NULL,
            dwh_updated_ts = @now
        WHERE ingestion_batch_id = @ingestion_batch_id
          AND source_object_id = @source_object_id;
    END;

    UPDATE control.ctl_object_run
    SET ingestion_batch_id = @ingestion_batch_id,
        landing_path = @landing_path,
        manifest_path = @manifest_path,
        bronze_commit_status = 'staged'
    WHERE pipeline_run_id = @pipeline_run_id
      AND source_object_id = @source_object_id
      AND run_status = 'running';

    SELECT CAST(1 AS BIT) AS can_write, 'stage_or_retry' AS batch_action;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_commit_bronze_batch
    @pipeline_run_id VARCHAR(100),
    @source_object_id INT,
    @ingestion_batch_id VARCHAR(128),
    @rows_landed BIGINT,
    @rows_committed BIGINT,
    @committed_watermark DATETIME2(3) = NULL,
    @committed_tie_breaker VARCHAR(200) = NULL,
    @committed_source_version VARCHAR(500) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();
    DECLARE @existing_status VARCHAR(30);

    SELECT @existing_status = batch_status
    FROM control.ctl_bronze_batch
    WHERE ingestion_batch_id = @ingestion_batch_id
      AND source_object_id = @source_object_id;

    IF @existing_status = 'committed'
    BEGIN
        SELECT CAST(0 AS BIT) AS committed_now, 'already_committed' AS batch_action;
        RETURN;
    END;

    IF @existing_status IS NULL
    BEGIN
        RAISERROR('The Bronze batch must be staged before it can be committed.', 16, 1);
        RETURN;
    END;

    UPDATE control.ctl_bronze_batch
    SET batch_status = 'committed',
        rows_landed = @rows_landed,
        rows_committed = @rows_committed,
        committed_ts = @now,
        error_message = NULL,
        dwh_updated_ts = @now
    WHERE ingestion_batch_id = @ingestion_batch_id
      AND source_object_id = @source_object_id;

    UPDATE control.ctl_object_run
    SET run_status = 'succeeded',
        run_completed_ts = @now,
        rows_read = @rows_landed,
        rows_written = @rows_committed,
        validation_status = 'passed',
        bronze_commit_status = 'committed',
        bronze_commit_ts = @now,
        error_category = NULL,
        error_message = NULL,
        retryable = CAST(0 AS BIT)
    WHERE pipeline_run_id = @pipeline_run_id
      AND source_object_id = @source_object_id
      AND run_status = 'running';

    UPDATE control.ctl_load_state
    SET load_status = 'ready',
        initial_load_completed = CAST(1 AS BIT),
        last_successful_watermark = COALESCE(@committed_watermark, last_successful_watermark),
        last_successful_tie_breaker = COALESCE(@committed_tie_breaker, last_successful_tie_breaker),
        last_successful_source_version = COALESCE(@committed_source_version, last_successful_source_version),
        last_committed_batch_id = @ingestion_batch_id,
        last_successful_run_id = @pipeline_run_id,
        last_success_ts = @now,
        lock_owner_run_id = NULL,
        lock_acquired_ts = NULL,
        lock_expires_ts = NULL,
        dwh_updated_ts = @now
    WHERE source_object_id = @source_object_id
      AND lock_owner_run_id = @pipeline_run_id;

    SELECT CAST(1 AS BIT) AS committed_now, 'committed' AS batch_action;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_fail_bronze_batch
    @pipeline_run_id VARCHAR(100),
    @source_object_id INT,
    @ingestion_batch_id VARCHAR(128),
    @error_category VARCHAR(100),
    @error_message VARCHAR(4000),
    @retryable BIT = 1
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();

    UPDATE control.ctl_bronze_batch
    SET batch_status = 'failed',
        error_message = @error_message,
        dwh_updated_ts = @now
    WHERE ingestion_batch_id = @ingestion_batch_id
      AND source_object_id = @source_object_id
      AND batch_status <> 'committed';

    UPDATE control.ctl_object_run
    SET bronze_commit_status = 'failed'
    WHERE pipeline_run_id = @pipeline_run_id
      AND source_object_id = @source_object_id
      AND ingestion_batch_id = @ingestion_batch_id
      AND run_status = 'running';

    EXEC control.sp_finish_object_run
        @pipeline_run_id = @pipeline_run_id,
        @source_object_id = @source_object_id,
        @run_status = 'failed',
        @validation_status = 'failed',
        @error_category = @error_category,
        @error_message = @error_message,
        @retryable = @retryable;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_log_schema_observation
    @pipeline_run_id VARCHAR(100),
    @source_object_id INT,
    @schema_contract_key BIGINT = NULL,
    @observed_schema_hash VARCHAR(128),
    @observed_schema_json VARCHAR(8000),
    @observed_column_count INT,
    @comparison_result VARCHAR(30),
    @comparison_detail VARCHAR(4000) = NULL,
    @drift_classification VARCHAR(50) = NULL,
    @severity VARCHAR(30) = NULL,
    @action_taken VARCHAR(100) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();
    DECLARE @schema_observation_key BIGINT;

    INSERT INTO control.ctl_schema_observation (
        pipeline_run_id, source_object_id, schema_contract_key, observed_schema_hash,
        observed_schema_json, observed_column_count, comparison_result,
        comparison_detail, observed_ts, dwh_created_ts
    )
    VALUES (
        @pipeline_run_id, @source_object_id, @schema_contract_key, @observed_schema_hash,
        @observed_schema_json, @observed_column_count, @comparison_result,
        @comparison_detail, @now, @now
    );

    -- The source-object lease prevents concurrent observations for this run.
    SELECT @schema_observation_key = MAX(schema_observation_key)
    FROM control.ctl_schema_observation
    WHERE pipeline_run_id = @pipeline_run_id
      AND source_object_id = @source_object_id
      AND observed_schema_hash = @observed_schema_hash;

    IF @comparison_result NOT IN ('exact_match', 'column_order_only')
    BEGIN
        INSERT INTO control.ctl_schema_drift_event (
            schema_observation_key, pipeline_run_id, source_object_id,
            expected_contract_version, expected_schema_hash, observed_schema_hash,
            drift_classification, severity, event_status, action_taken,
            event_detail, opened_ts, resolved_ts, resolved_by, resolution_note,
            dwh_created_ts, dwh_updated_ts
        )
        SELECT @schema_observation_key, @pipeline_run_id, @source_object_id,
               c.contract_version, c.expected_schema_hash, @observed_schema_hash,
               COALESCE(@drift_classification, @comparison_result),
               COALESCE(@severity, 'warning'), 'open',
               COALESCE(@action_taken, 'review_required'), @comparison_detail,
               @now, NULL, NULL, NULL, @now, @now
        FROM control.ctl_schema_contract c
        WHERE c.source_object_id = @source_object_id
          AND c.contract_status = 'approved'
          AND c.effective_to_ts IS NULL;
    END;

    SELECT @schema_observation_key AS schema_observation_key;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_log_quality_result
    @pipeline_run_id VARCHAR(100),
    @source_object_id INT,
    @ingestion_batch_id VARCHAR(128) = NULL,
    @check_name VARCHAR(200),
    @check_scope VARCHAR(50),
    @severity VARCHAR(30),
    @threshold_value DECIMAL(28,6) = NULL,
    @observed_value DECIMAL(28,6) = NULL,
    @result_status VARCHAR(30),
    @result_detail VARCHAR(4000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO control.ctl_quality_result (
        pipeline_run_id, source_object_id, ingestion_batch_id, check_name,
        check_scope, severity, threshold_value, observed_value, result_status,
        result_detail, checked_ts, dwh_created_ts
    )
    VALUES (
        @pipeline_run_id, @source_object_id, @ingestion_batch_id, @check_name,
        @check_scope, @severity, @threshold_value, @observed_value, @result_status,
        @result_detail, SYSUTCDATETIME(), SYSUTCDATETIME()
    );
END;
GO

CREATE OR ALTER VIEW control.vw_open_operational_alerts
AS
SELECT
    'schema_drift' AS alert_type,
    d.severity,
    d.source_object_id,
    d.pipeline_run_id,
    d.opened_ts AS alert_ts,
    d.drift_classification AS alert_code,
    d.event_detail AS alert_detail
FROM control.ctl_schema_drift_event d
WHERE d.event_status = 'open'
UNION ALL
SELECT
    'quality_failure' AS alert_type,
    q.severity,
    q.source_object_id,
    q.pipeline_run_id,
    q.checked_ts AS alert_ts,
    q.check_name AS alert_code,
    q.result_detail AS alert_detail
FROM control.ctl_quality_result q
WHERE q.result_status = 'failed'
UNION ALL
SELECT
    'bronze_batch_failure' AS alert_type,
    'error' AS severity,
    b.source_object_id,
    b.pipeline_run_id,
    b.dwh_updated_ts AS alert_ts,
    'bronze_batch_failed' AS alert_code,
    b.error_message AS alert_detail
FROM control.ctl_bronze_batch b
WHERE b.batch_status = 'failed';
GO
