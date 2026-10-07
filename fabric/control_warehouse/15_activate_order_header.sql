-- Activate after the Bronze guard and dedicated child pipeline are deployed.
UPDATE control.ctl_source_object
SET is_active = CAST(1 AS bit), dwh_updated_ts = SYSUTCDATETIME()
WHERE source_object_id = 1007 AND is_active = 0;
GO
