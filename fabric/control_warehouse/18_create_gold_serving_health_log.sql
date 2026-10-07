-- Append-only post-Gold checks. One row records the consumer-facing result of
-- each check, including failures; the daily parent fails when a check fails.
IF OBJECT_ID('control.ctl_gold_serving_health_run', 'U') IS NULL
BEGIN
    CREATE TABLE control.ctl_gold_serving_health_run (
        health_run_id         VARCHAR(36) NOT NULL,
        pipeline_run_id       VARCHAR(100) NOT NULL,
        checked_at_utc        DATETIME2(3) NOT NULL,
        gold_audited_at_utc   DATETIME2(3) NULL,
        model_audited_at_utc  DATETIME2(3) NULL,
        check_status          VARCHAR(20) NOT NULL,
        failure_reason        VARCHAR(2000) NULL,
        comparison_json       VARCHAR(4000) NOT NULL
    );
END;
GO
