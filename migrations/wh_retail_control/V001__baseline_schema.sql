-- Catalog-only export. Creates missing objects; never drops data or resets state.

IF SCHEMA_ID('control') IS NULL EXEC('CREATE SCHEMA [control]');
GO

IF OBJECT_ID('control.ctl_bronze_batch', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_bronze_batch] (
    [bronze_batch_key] bigint IDENTITY NOT NULL,
    [ingestion_batch_id] varchar(128) NOT NULL,
    [source_object_id] int NOT NULL,
    [pipeline_run_id] varchar(100) NOT NULL,
    [source_version] varchar(500) NULL,
    [lower_watermark] datetime2(3) NULL,
    [upper_watermark] datetime2(3) NULL,
    [lower_tie_breaker] varchar(200) NULL,
    [upper_tie_breaker] varchar(200) NULL,
    [landing_path] varchar(1000) NOT NULL,
    [manifest_path] varchar(1000) NOT NULL,
    [bronze_target_name] varchar(256) NOT NULL,
    [batch_status] varchar(30) NOT NULL,
    [rows_landed] bigint NULL,
    [rows_committed] bigint NULL,
    [committed_ts] datetime2(3) NULL,
    [error_message] varchar(4000) NULL,
    [dwh_created_ts] datetime2(3) NOT NULL,
    [dwh_updated_ts] datetime2(3) NOT NULL,
    [rows_expected] bigint NULL,
    [manifest_written] bit NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_connection', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_connection] (
    [connection_id] int NOT NULL,
    [source_system_id] int NOT NULL,
    [connection_name] varchar(200) NOT NULL,
    [connection_type] varchar(100) NOT NULL,
    [gateway_name] varchar(200) NULL,
    [environment_name] varchar(50) NOT NULL,
    [authentication_mode] varchar(100) NULL,
    [connection_owner] varchar(200) NULL,
    [is_active] bit NOT NULL,
    [dwh_created_ts] datetime2(3) NOT NULL,
    [dwh_updated_ts] datetime2(3) NOT NULL,
    [fabric_connection_id] varchar(100) NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_fact_rekey_queue', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_fact_rekey_queue] (
    [fact_rekey_queue_key] bigint IDENTITY NOT NULL,
    [pipeline_run_id] varchar(100) NOT NULL,
    [fact_table_name] varchar(256) NOT NULL,
    [dimension_name] varchar(256) NOT NULL,
    [dimension_entity_key] varchar(200) NOT NULL,
    [affected_from_date] date NOT NULL,
    [affected_to_date] date NOT NULL,
    [queue_status] varchar(30) NOT NULL,
    [rows_rekeyed] bigint NULL,
    [error_message] varchar(4000) NULL,
    [queued_ts] datetime2(3) NOT NULL,
    [processed_ts] datetime2(3) NULL,
    [dwh_updated_ts] datetime2(3) NOT NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_gold_serving_health_run', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_gold_serving_health_run] (
    [health_run_id] varchar(36) NOT NULL,
    [pipeline_run_id] varchar(100) NOT NULL,
    [checked_at_utc] datetime2(3) NOT NULL,
    [gold_audited_at_utc] datetime2(3) NULL,
    [model_audited_at_utc] datetime2(3) NULL,
    [check_status] varchar(20) NOT NULL,
    [failure_reason] varchar(2000) NULL,
    [comparison_json] varchar(4000) NOT NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_load_state', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_load_state] (
    [source_object_id] int NOT NULL,
    [load_status] varchar(30) NOT NULL,
    [initial_load_completed] bit NOT NULL,
    [last_successful_watermark] datetime2(3) NULL,
    [last_successful_tie_breaker] varchar(200) NULL,
    [last_successful_source_version] varchar(500) NULL,
    [last_successful_run_id] varchar(100) NULL,
    [last_success_ts] datetime2(3) NULL,
    [lock_owner_run_id] varchar(100) NULL,
    [lock_acquired_ts] datetime2(3) NULL,
    [lock_expires_ts] datetime2(3) NULL,
    [dwh_updated_ts] datetime2(3) NOT NULL,
    [last_committed_batch_id] varchar(128) NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_object_run', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_object_run] (
    [object_run_key] bigint IDENTITY NOT NULL,
    [pipeline_run_id] varchar(100) NOT NULL,
    [source_object_id] int NOT NULL,
    [attempt_number] int NOT NULL,
    [run_status] varchar(30) NOT NULL,
    [run_started_ts] datetime2(3) NOT NULL,
    [run_completed_ts] datetime2(3) NULL,
    [lower_watermark] datetime2(3) NULL,
    [upper_watermark] datetime2(3) NULL,
    [lower_tie_breaker] varchar(200) NULL,
    [upper_tie_breaker] varchar(200) NULL,
    [source_version] varchar(500) NULL,
    [rows_read] bigint NULL,
    [rows_written] bigint NULL,
    [rows_rejected] bigint NULL,
    [validation_status] varchar(30) NULL,
    [error_category] varchar(100) NULL,
    [error_message] varchar(4000) NULL,
    [retryable] bit NULL,
    [dwh_created_ts] datetime2(3) NOT NULL,
    [ingestion_batch_id] varchar(128) NULL,
    [landing_path] varchar(1000) NULL,
    [manifest_path] varchar(1000) NULL,
    [observed_schema_hash] varchar(128) NULL,
    [bronze_commit_status] varchar(30) NULL,
    [bronze_commit_ts] datetime2(3) NULL,
    [parent_pipeline_run_id] varchar(100) NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_pipeline_run', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_pipeline_run] (
    [pipeline_run_id] varchar(100) NOT NULL,
    [pipeline_name] varchar(200) NOT NULL,
    [trigger_type] varchar(50) NOT NULL,
    [trigger_name] varchar(200) NULL,
    [run_status] varchar(30) NOT NULL,
    [run_started_ts] datetime2(3) NOT NULL,
    [run_completed_ts] datetime2(3) NULL,
    [requested_by] varchar(200) NULL,
    [correlation_id] varchar(100) NULL,
    [objects_requested] int NOT NULL,
    [objects_succeeded] int NOT NULL,
    [objects_failed] int NOT NULL,
    [error_message] varchar(4000) NULL,
    [dwh_created_ts] datetime2(3) NOT NULL,
    [objects_skipped] int NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_quality_result', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_quality_result] (
    [quality_result_key] bigint IDENTITY NOT NULL,
    [pipeline_run_id] varchar(100) NOT NULL,
    [source_object_id] int NOT NULL,
    [ingestion_batch_id] varchar(128) NULL,
    [check_name] varchar(200) NOT NULL,
    [check_scope] varchar(50) NOT NULL,
    [severity] varchar(30) NOT NULL,
    [threshold_value] decimal(28,6) NULL,
    [observed_value] decimal(28,6) NULL,
    [result_status] varchar(30) NOT NULL,
    [result_detail] varchar(4000) NULL,
    [checked_ts] datetime2(3) NOT NULL,
    [dwh_created_ts] datetime2(3) NOT NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_schema_contract', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_schema_contract] (
    [schema_contract_key] bigint IDENTITY NOT NULL,
    [source_object_id] int NOT NULL,
    [contract_version] int NOT NULL,
    [contract_status] varchar(30) NOT NULL,
    [drift_action] varchar(50) NOT NULL,
    [expected_columns_csv] varchar(4000) NOT NULL,
    [expected_schema_hash] varchar(128) NULL,
    [effective_from_ts] datetime2(3) NOT NULL,
    [effective_to_ts] datetime2(3) NULL,
    [approved_by] varchar(200) NULL,
    [dwh_created_ts] datetime2(3) NOT NULL,
    [expected_schema_json] varchar(8000) NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_schema_drift_event', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_schema_drift_event] (
    [schema_drift_event_key] bigint IDENTITY NOT NULL,
    [schema_observation_key] bigint NOT NULL,
    [pipeline_run_id] varchar(100) NOT NULL,
    [source_object_id] int NOT NULL,
    [expected_contract_version] int NULL,
    [expected_schema_hash] varchar(128) NULL,
    [observed_schema_hash] varchar(128) NOT NULL,
    [drift_classification] varchar(50) NOT NULL,
    [severity] varchar(30) NOT NULL,
    [event_status] varchar(30) NOT NULL,
    [action_taken] varchar(100) NOT NULL,
    [event_detail] varchar(4000) NULL,
    [opened_ts] datetime2(3) NOT NULL,
    [resolved_ts] datetime2(3) NULL,
    [resolved_by] varchar(200) NULL,
    [resolution_note] varchar(4000) NULL,
    [dwh_created_ts] datetime2(3) NOT NULL,
    [dwh_updated_ts] datetime2(3) NOT NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_schema_observation', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_schema_observation] (
    [schema_observation_key] bigint IDENTITY NOT NULL,
    [pipeline_run_id] varchar(100) NOT NULL,
    [source_object_id] int NOT NULL,
    [schema_contract_key] bigint NULL,
    [observed_schema_hash] varchar(128) NOT NULL,
    [observed_schema_json] varchar(8000) NOT NULL,
    [observed_column_count] int NOT NULL,
    [comparison_result] varchar(30) NOT NULL,
    [comparison_detail] varchar(4000) NULL,
    [observed_ts] datetime2(3) NOT NULL,
    [dwh_created_ts] datetime2(3) NOT NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_source_object', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_source_object] (
    [source_object_id] int NOT NULL,
    [source_system_id] int NOT NULL,
    [connection_id] int NOT NULL,
    [source_object_name] varchar(500) NOT NULL,
    [source_object_type] varchar(50) NOT NULL,
    [source_locator] varchar(1000) NOT NULL,
    [source_schema_name] varchar(128) NULL,
    [source_table_name] varchar(256) NULL,
    [bronze_lakehouse_name] varchar(200) NOT NULL,
    [bronze_target_name] varchar(256) NOT NULL,
    [load_strategy] varchar(50) NOT NULL,
    [initial_write_behavior] varchar(50) NOT NULL,
    [incremental_write_behavior] varchar(50) NULL,
    [watermark_column] varchar(128) NULL,
    [tie_breaker_column] varchar(128) NULL,
    [watermark_lookback_seconds] int NOT NULL,
    [load_group] varchar(100) NOT NULL,
    [sequence_order] int NOT NULL,
    [max_parallelism] int NOT NULL,
    [retry_limit] int NOT NULL,
    [is_active] bit NOT NULL,
    [dwh_created_ts] datetime2(3) NOT NULL,
    [dwh_updated_ts] datetime2(3) NOT NULL,
    [landing_relative_path] varchar(1000) NULL,
    [manifest_relative_path] varchar(1000) NULL,
    [quality_profile_code] varchar(100) NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_source_system', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_source_system] (
    [source_system_id] int NOT NULL,
    [source_system_code] varchar(100) NOT NULL,
    [source_system_name] varchar(200) NOT NULL,
    [source_engine] varchar(100) NOT NULL,
    [source_role] varchar(50) NOT NULL,
    [data_owner] varchar(200) NULL,
    [data_classification] varchar(50) NOT NULL,
    [is_active] bit NOT NULL,
    [dwh_created_ts] datetime2(3) NOT NULL,
    [dwh_updated_ts] datetime2(3) NOT NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_transform_object', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_transform_object] (
    [transform_object_id] int NOT NULL,
    [transform_name] varchar(200) NOT NULL,
    [target_lakehouse_name] varchar(200) NOT NULL,
    [target_schema_name] varchar(128) NOT NULL,
    [target_table_name] varchar(256) NOT NULL,
    [notebook_name] varchar(200) NOT NULL,
    [processing_group] varchar(100) NOT NULL,
    [sequence_order] int NOT NULL,
    [processing_strategy] varchar(50) NOT NULL,
    [source_object_ids_csv] varchar(500) NOT NULL,
    [natural_key_columns_csv] varchar(1000) NOT NULL,
    [is_active] bit NOT NULL,
    [dwh_created_ts] datetime2(3) NOT NULL,
    [dwh_updated_ts] datetime2(3) NOT NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_transform_run', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_transform_run] (
    [transform_run_key] bigint IDENTITY NOT NULL,
    [pipeline_run_id] varchar(100) NOT NULL,
    [transform_object_id] int NOT NULL,
    [run_status] varchar(30) NOT NULL,
    [load_mode] varchar(30) NOT NULL,
    [run_started_ts] datetime2(3) NOT NULL,
    [run_completed_ts] datetime2(3) NULL,
    [lower_bronze_batch_key] bigint NULL,
    [upper_bronze_batch_key] bigint NULL,
    [rows_read] bigint NULL,
    [rows_inserted] bigint NULL,
    [rows_updated] bigint NULL,
    [rows_rejected] bigint NULL,
    [rows_inferred] bigint NULL,
    [rows_rekeyed] bigint NULL,
    [validation_status] varchar(30) NULL,
    [error_message] varchar(4000) NULL,
    [dwh_created_ts] datetime2(3) NOT NULL
  );
END;
GO

IF OBJECT_ID('control.ctl_transform_state', 'U') IS NULL
BEGIN
  CREATE TABLE [control].[ctl_transform_state] (
    [transform_object_id] int NOT NULL,
    [transform_status] varchar(30) NOT NULL,
    [baseline_completed] bit NOT NULL,
    [last_processed_bronze_batch_key] bigint NOT NULL,
    [last_successful_run_id] varchar(100) NULL,
    [last_success_ts] datetime2(3) NULL,
    [lock_owner_run_id] varchar(100) NULL,
    [lock_acquired_ts] datetime2(3) NULL,
    [lock_expires_ts] datetime2(3) NULL,
    [dwh_updated_ts] datetime2(3) NOT NULL
  );
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

CREATE OR ALTER VIEW control.vw_active_source_objects AS
SELECT o.source_object_id, ss.source_system_code, ss.source_engine, ss.source_role, c.connection_name, c.connection_type, c.gateway_name, o.source_object_name, o.source_object_type, o.source_locator, o.source_schema_name, o.source_table_name, o.bronze_lakehouse_name, o.bronze_target_name, o.load_strategy, o.initial_write_behavior, o.incremental_write_behavior, o.watermark_column, o.tie_breaker_column, o.watermark_lookback_seconds, o.load_group, o.sequence_order, o.max_parallelism, o.retry_limit, s.initial_load_completed, s.last_successful_watermark, s.last_successful_tie_breaker, s.last_successful_source_version, s.last_successful_run_id, s.last_success_ts, s.load_status, sc.contract_version, sc.drift_action, sc.expected_columns_csv
FROM control.ctl_source_object o
INNER JOIN control.ctl_source_system ss ON ss.source_system_id=o.source_system_id
INNER JOIN control.ctl_connection c ON c.connection_id=o.connection_id
INNER JOIN control.ctl_load_state s ON s.source_object_id=o.source_object_id
LEFT JOIN control.ctl_schema_contract sc ON sc.source_object_id=o.source_object_id AND sc.contract_status='approved' AND sc.effective_to_ts IS NULL
WHERE o.is_active=CAST(1 AS BIT) AND ss.is_active=CAST(1 AS BIT) AND c.is_active=CAST(1 AS BIT);
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

CREATE OR ALTER VIEW control.vw_recent_control_failures AS SELECT TOP 500 pr.pipeline_run_id,pr.pipeline_name,pr.run_started_ts AS pipeline_started_ts,oru.source_object_id,so.source_object_name,oru.attempt_number,oru.run_status,oru.error_category,oru.error_message,oru.retryable,oru.run_completed_ts FROM control.ctl_object_run oru INNER JOIN control.ctl_pipeline_run pr ON pr.pipeline_run_id=oru.pipeline_run_id INNER JOIN control.ctl_source_object so ON so.source_object_id=oru.source_object_id WHERE oru.run_status IN ('failed','skipped') ORDER BY oru.run_completed_ts DESC;
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

CREATE OR ALTER PROCEDURE control.sp_finish_object_run
@pipeline_run_id VARCHAR(100), @source_object_id INT, @run_status VARCHAR(30), @rows_read BIGINT = NULL, @rows_written BIGINT = NULL, @rows_rejected BIGINT = NULL, @validation_status VARCHAR(30) = NULL, @error_category VARCHAR(100) = NULL, @error_message VARCHAR(4000) = NULL, @retryable BIT = NULL, @committed_watermark DATETIME2(3) = NULL, @committed_tie_breaker VARCHAR(200) = NULL, @committed_source_version VARCHAR(500) = NULL
AS
BEGIN
SET NOCOUNT ON;
DECLARE @now DATETIME2(3)=SYSUTCDATETIME();
UPDATE control.ctl_object_run SET run_status=@run_status,run_completed_ts=@now,rows_read=@rows_read,rows_written=@rows_written,rows_rejected=@rows_rejected,validation_status=@validation_status,error_category=@error_category,error_message=@error_message,retryable=@retryable WHERE pipeline_run_id=@pipeline_run_id AND source_object_id=@source_object_id AND run_status='running';
IF @run_status='succeeded'
BEGIN
UPDATE control.ctl_load_state SET load_status='ready',initial_load_completed=CAST(1 AS BIT),last_successful_watermark=COALESCE(@committed_watermark,last_successful_watermark),last_successful_tie_breaker=COALESCE(@committed_tie_breaker,last_successful_tie_breaker),last_successful_source_version=COALESCE(@committed_source_version,last_successful_source_version),last_successful_run_id=@pipeline_run_id,last_success_ts=@now,lock_owner_run_id=NULL,lock_acquired_ts=NULL,lock_expires_ts=NULL,dwh_updated_ts=@now WHERE source_object_id=@source_object_id AND lock_owner_run_id=@pipeline_run_id;
END
ELSE
BEGIN
UPDATE control.ctl_load_state SET load_status='ready',lock_owner_run_id=NULL,lock_acquired_ts=NULL,lock_expires_ts=NULL,dwh_updated_ts=@now WHERE source_object_id=@source_object_id AND lock_owner_run_id=@pipeline_run_id;
END;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_finish_pipeline_run
@pipeline_run_id VARCHAR(100), @run_status VARCHAR(30), @error_message VARCHAR(4000) = NULL
AS
BEGIN
SET NOCOUNT ON;
UPDATE control.ctl_pipeline_run SET run_status=@run_status,run_completed_ts=SYSUTCDATETIME(),objects_succeeded=(SELECT COUNT(*) FROM control.ctl_object_run WHERE pipeline_run_id=@pipeline_run_id AND run_status='succeeded'),objects_failed=(SELECT COUNT(*) FROM control.ctl_object_run WHERE pipeline_run_id=@pipeline_run_id AND run_status='failed'),objects_skipped=(SELECT COUNT(*) FROM control.ctl_object_run WHERE pipeline_run_id=@pipeline_run_id AND run_status='skipped'),error_message=@error_message WHERE pipeline_run_id=@pipeline_run_id;
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

CREATE OR ALTER PROCEDURE control.sp_start_object_run
@pipeline_run_id VARCHAR(100), @source_object_id INT, @attempt_number INT = 1, @lower_watermark DATETIME2(3) = NULL, @upper_watermark DATETIME2(3) = NULL, @lower_tie_breaker VARCHAR(200) = NULL, @upper_tie_breaker VARCHAR(200) = NULL, @source_version VARCHAR(500) = NULL, @lease_minutes INT = 120
AS
BEGIN
SET NOCOUNT ON;
DECLARE @now DATETIME2(3)=SYSUTCDATETIME();
DECLARE @lock_acquired INT;
UPDATE control.ctl_load_state SET load_status='running',lock_owner_run_id=@pipeline_run_id,lock_acquired_ts=@now,lock_expires_ts=DATEADD(MINUTE,@lease_minutes,@now),dwh_updated_ts=@now WHERE source_object_id=@source_object_id AND (lock_owner_run_id IS NULL OR lock_owner_run_id=@pipeline_run_id OR lock_expires_ts<=@now);
SET @lock_acquired=@@ROWCOUNT;
IF @lock_acquired=1
BEGIN
INSERT INTO control.ctl_object_run (pipeline_run_id,source_object_id,attempt_number,run_status,run_started_ts,run_completed_ts,lower_watermark,upper_watermark,lower_tie_breaker,upper_tie_breaker,source_version,rows_read,rows_written,rows_rejected,validation_status,error_category,error_message,retryable,dwh_created_ts) VALUES (@pipeline_run_id,@source_object_id,@attempt_number,'running',@now,NULL,@lower_watermark,@upper_watermark,@lower_tie_breaker,@upper_tie_breaker,@source_version,NULL,NULL,NULL,NULL,NULL,NULL,NULL,@now);
END
ELSE
BEGIN
INSERT INTO control.ctl_object_run (pipeline_run_id,source_object_id,attempt_number,run_status,run_started_ts,run_completed_ts,lower_watermark,upper_watermark,lower_tie_breaker,upper_tie_breaker,source_version,rows_read,rows_written,rows_rejected,validation_status,error_category,error_message,retryable,dwh_created_ts) VALUES (@pipeline_run_id,@source_object_id,@attempt_number,'skipped',@now,@now,@lower_watermark,@upper_watermark,@lower_tie_breaker,@upper_tie_breaker,@source_version,NULL,NULL,NULL,'not_run','concurrency_lock','The source object is already locked by another pipeline run.',1,@now);
END;
SELECT CAST(CASE WHEN @lock_acquired=1 THEN 1 ELSE 0 END AS BIT) AS lock_acquired,@source_object_id AS source_object_id,@pipeline_run_id AS pipeline_run_id;
END;
GO

CREATE OR ALTER PROCEDURE control.sp_start_pipeline_run
@pipeline_run_id VARCHAR(100), @pipeline_name VARCHAR(200), @trigger_type VARCHAR(50), @trigger_name VARCHAR(200) = NULL, @requested_by VARCHAR(200) = NULL, @correlation_id VARCHAR(100) = NULL, @objects_requested INT = 0
AS
BEGIN
SET NOCOUNT ON;
INSERT INTO control.ctl_pipeline_run (pipeline_run_id,pipeline_name,trigger_type,trigger_name,run_status,run_started_ts,run_completed_ts,requested_by,correlation_id,objects_requested,objects_succeeded,objects_failed,objects_skipped,error_message,dwh_created_ts)
SELECT @pipeline_run_id,@pipeline_name,@trigger_type,@trigger_name,'running',SYSUTCDATETIME(),NULL,@requested_by,@correlation_id,@objects_requested,0,0,0,NULL,SYSUTCDATETIME()
WHERE NOT EXISTS (SELECT 1 FROM control.ctl_pipeline_run WHERE pipeline_run_id=@pipeline_run_id);
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
