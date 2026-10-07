-- Operational stored procedures and views for wh_retail_control.

CREATE OR ALTER PROCEDURE control.sp_start_pipeline_run
    @pipeline_run_id VARCHAR(100),
    @pipeline_name VARCHAR(200),
    @trigger_type VARCHAR(50),
    @trigger_name VARCHAR(200) = NULL,
    @requested_by VARCHAR(200) = NULL,
    @correlation_id VARCHAR(100) = NULL,
    @objects_requested INT = 0
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO control.ctl_pipeline_run (
        pipeline_run_id, pipeline_name, trigger_type, trigger_name, run_status,
        run_started_ts, run_completed_ts, requested_by, correlation_id,
        objects_requested, objects_succeeded, objects_failed, objects_skipped, error_message, dwh_created_ts
    )
    SELECT @pipeline_run_id, @pipeline_name, @trigger_type, @trigger_name, 'running',
           SYSUTCDATETIME(), NULL, @requested_by, @correlation_id,
           @objects_requested, 0, 0, 0, NULL, SYSUTCDATETIME()
    WHERE NOT EXISTS (
        SELECT 1 FROM control.ctl_pipeline_run WHERE pipeline_run_id = @pipeline_run_id
    );
END;
GO

CREATE OR ALTER PROCEDURE control.sp_start_object_run
    @pipeline_run_id VARCHAR(100),
    @source_object_id INT,
    @attempt_number INT = 1,
    @lower_watermark DATETIME2(3) = NULL,
    @upper_watermark DATETIME2(3) = NULL,
    @lower_tie_breaker VARCHAR(200) = NULL,
    @upper_tie_breaker VARCHAR(200) = NULL,
    @source_version VARCHAR(500) = NULL,
    @lease_minutes INT = 120
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();
    DECLARE @lock_acquired INT;

    UPDATE control.ctl_load_state
    SET load_status = 'running',
        lock_owner_run_id = @pipeline_run_id,
        lock_acquired_ts = @now,
        lock_expires_ts = DATEADD(MINUTE, @lease_minutes, @now),
        dwh_updated_ts = @now
    WHERE source_object_id = @source_object_id
      AND (
          lock_owner_run_id IS NULL
          OR lock_owner_run_id = @pipeline_run_id
          OR lock_expires_ts <= @now
      );

    SET @lock_acquired = @@ROWCOUNT;

    IF @lock_acquired = 1
    BEGIN
        INSERT INTO control.ctl_object_run (
            pipeline_run_id, source_object_id, attempt_number, run_status, run_started_ts,
            run_completed_ts, lower_watermark, upper_watermark, lower_tie_breaker,
            upper_tie_breaker, source_version, rows_read, rows_written, rows_rejected,
            validation_status, error_category, error_message, retryable, dwh_created_ts
        )
        VALUES (
            @pipeline_run_id, @source_object_id, @attempt_number, 'running', @now,
            NULL, @lower_watermark, @upper_watermark, @lower_tie_breaker,
            @upper_tie_breaker, @source_version, NULL, NULL, NULL,
            NULL, NULL, NULL, NULL, @now
        );
    END;
    ELSE
    BEGIN
        INSERT INTO control.ctl_object_run (
            pipeline_run_id, source_object_id, attempt_number, run_status, run_started_ts,
            run_completed_ts, lower_watermark, upper_watermark, lower_tie_breaker,
            upper_tie_breaker, source_version, rows_read, rows_written, rows_rejected,
            validation_status, error_category, error_message, retryable, dwh_created_ts
        )
        VALUES (
            @pipeline_run_id, @source_object_id, @attempt_number, 'skipped', @now,
            @now, @lower_watermark, @upper_watermark, @lower_tie_breaker,
            @upper_tie_breaker, @source_version, NULL, NULL, NULL,
            'not_run', 'concurrency_lock', 'The source object is already locked by another pipeline run.', 1, @now
        );
    END;

    SELECT
        CAST(CASE WHEN @lock_acquired = 1 THEN 1 ELSE 0 END AS BIT) AS lock_acquired,
        @source_object_id AS source_object_id,
        @pipeline_run_id AS pipeline_run_id;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_finish_object_run
    @pipeline_run_id VARCHAR(100),
    @source_object_id INT,
    @run_status VARCHAR(30),
    @rows_read BIGINT = NULL,
    @rows_written BIGINT = NULL,
    @rows_rejected BIGINT = NULL,
    @validation_status VARCHAR(30) = NULL,
    @error_category VARCHAR(100) = NULL,
    @error_message VARCHAR(4000) = NULL,
    @retryable BIT = NULL,
    @committed_watermark DATETIME2(3) = NULL,
    @committed_tie_breaker VARCHAR(200) = NULL,
    @committed_source_version VARCHAR(500) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @now DATETIME2(3) = SYSUTCDATETIME();

    UPDATE control.ctl_object_run
    SET run_status = @run_status,
        run_completed_ts = @now,
        rows_read = @rows_read,
        rows_written = @rows_written,
        rows_rejected = @rows_rejected,
        validation_status = @validation_status,
        error_category = @error_category,
        error_message = @error_message,
        retryable = @retryable
    WHERE pipeline_run_id = @pipeline_run_id
      AND source_object_id = @source_object_id
      AND run_status = 'running';

    IF @run_status = 'succeeded'
    BEGIN
        UPDATE control.ctl_load_state
        SET load_status = 'ready',
            initial_load_completed = CAST(1 AS BIT),
            last_successful_watermark = COALESCE(@committed_watermark, last_successful_watermark),
            last_successful_tie_breaker = COALESCE(@committed_tie_breaker, last_successful_tie_breaker),
            last_successful_source_version = COALESCE(@committed_source_version, last_successful_source_version),
            last_successful_run_id = @pipeline_run_id,
            last_success_ts = @now,
            lock_owner_run_id = NULL,
            lock_acquired_ts = NULL,
            lock_expires_ts = NULL,
            dwh_updated_ts = @now
        WHERE source_object_id = @source_object_id
          AND lock_owner_run_id = @pipeline_run_id;
    END;
    ELSE
    BEGIN
        UPDATE control.ctl_load_state
        SET load_status = 'ready',
            lock_owner_run_id = NULL,
            lock_acquired_ts = NULL,
            lock_expires_ts = NULL,
            dwh_updated_ts = @now
        WHERE source_object_id = @source_object_id
          AND lock_owner_run_id = @pipeline_run_id;
    END;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_finish_pipeline_run
    @pipeline_run_id VARCHAR(100),
    @run_status VARCHAR(30),
    @error_message VARCHAR(4000) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE control.ctl_pipeline_run
    SET run_status = @run_status,
        run_completed_ts = SYSUTCDATETIME(),
        objects_succeeded = (
            SELECT COUNT(*) FROM control.ctl_object_run
            WHERE pipeline_run_id = @pipeline_run_id AND run_status = 'succeeded'
        ),
        objects_failed = (
            SELECT COUNT(*) FROM control.ctl_object_run
            WHERE pipeline_run_id = @pipeline_run_id AND run_status = 'failed'
        ),
        objects_skipped = (
            SELECT COUNT(*) FROM control.ctl_object_run
            WHERE pipeline_run_id = @pipeline_run_id AND run_status = 'skipped'
        ),
        error_message = @error_message
    WHERE pipeline_run_id = @pipeline_run_id;
END;
GO

CREATE OR ALTER VIEW control.vw_active_source_objects
AS
SELECT
    o.source_object_id,
    ss.source_system_code,
    ss.source_engine,
    ss.source_role,
    c.connection_name,
    c.connection_type,
    c.gateway_name,
    o.source_object_name,
    o.source_object_type,
    o.source_locator,
    o.source_schema_name,
    o.source_table_name,
    o.bronze_lakehouse_name,
    o.bronze_target_name,
    o.load_strategy,
    o.initial_write_behavior,
    o.incremental_write_behavior,
    o.watermark_column,
    o.tie_breaker_column,
    o.watermark_lookback_seconds,
    o.load_group,
    o.sequence_order,
    o.max_parallelism,
    o.retry_limit,
    s.initial_load_completed,
    s.last_successful_watermark,
    s.last_successful_tie_breaker,
    s.last_successful_source_version,
    s.last_successful_run_id,
    s.last_success_ts,
    s.load_status,
    sc.contract_version,
    sc.drift_action,
    sc.expected_columns_csv
FROM control.ctl_source_object o
INNER JOIN control.ctl_source_system ss
    ON ss.source_system_id = o.source_system_id
INNER JOIN control.ctl_connection c
    ON c.connection_id = o.connection_id
INNER JOIN control.ctl_load_state s
    ON s.source_object_id = o.source_object_id
LEFT JOIN control.ctl_schema_contract sc
    ON sc.source_object_id = o.source_object_id
   AND sc.contract_status = 'approved'
   AND sc.effective_to_ts IS NULL
WHERE o.is_active = CAST(1 AS BIT)
  AND ss.is_active = CAST(1 AS BIT)
  AND c.is_active = CAST(1 AS BIT);
GO

CREATE OR ALTER VIEW control.vw_recent_control_failures
AS
SELECT TOP 500
    pr.pipeline_run_id,
    pr.pipeline_name,
    pr.run_started_ts AS pipeline_started_ts,
    oru.source_object_id,
    so.source_object_name,
    oru.attempt_number,
    oru.run_status,
    oru.error_category,
    oru.error_message,
    oru.retryable,
    oru.run_completed_ts
FROM control.ctl_object_run oru
INNER JOIN control.ctl_pipeline_run pr
    ON pr.pipeline_run_id = oru.pipeline_run_id
INNER JOIN control.ctl_source_object so
    ON so.source_object_id = oru.source_object_id
WHERE oru.run_status IN ('failed', 'skipped')
ORDER BY oru.run_completed_ts DESC;
GO
