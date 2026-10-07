-- Enable only after pg_order_header Bronze baseline has committed.
UPDATE control.ctl_transform_object
SET is_active = CAST(1 AS bit), dwh_updated_ts = SYSUTCDATETIME()
WHERE transform_object_id = 3011 AND is_active = 0;
GO
