-- One-time cleanup for wh_retail_control before the enterprise control plane.
-- Approved for this project because no production pipeline history exists yet.

IF OBJECT_ID('control.ctl_pipeline_run_log', 'U') IS NOT NULL
    DROP TABLE control.ctl_pipeline_run_log;
GO
IF OBJECT_ID('control.ctl_watermark_state', 'U') IS NOT NULL
    DROP TABLE control.ctl_watermark_state;
GO
IF OBJECT_ID('control.ctl_source_config', 'U') IS NOT NULL
    DROP TABLE control.ctl_source_config;
GO
IF OBJECT_ID('control.s3_snapshot_audit', 'U') IS NOT NULL
    DROP TABLE control.s3_snapshot_audit;
GO
IF OBJECT_ID('control.pipeline_run_audit', 'U') IS NOT NULL
    DROP TABLE control.pipeline_run_audit;
GO
IF OBJECT_ID('control.ingestion_watermark', 'U') IS NOT NULL
    DROP TABLE control.ingestion_watermark;
GO
IF OBJECT_ID('control.source_object', 'U') IS NOT NULL
    DROP TABLE control.source_object;
GO
IF OBJECT_ID('control.source_system', 'U') IS NOT NULL
    DROP TABLE control.source_system;
GO
