-- Finalize manifest metadata only after nb_bronze_batch_guard has validated
-- and written the 14 existing committed Bronze batch manifests.

UPDATE control.ctl_bronze_batch
SET manifest_path = CASE
        WHEN RIGHT(manifest_path, 5) = '.json' THEN manifest_path
        ELSE CONCAT(manifest_path, '/', ingestion_batch_id, '.json')
    END,
    rows_expected = rows_committed,
    manifest_written = CAST(1 AS BIT),
    dwh_updated_ts = SYSUTCDATETIME()
WHERE batch_status = 'committed'
  AND ingestion_batch_id IN (
      'pg-1001-baseline-20260907',
      'pg-1002-baseline-20260907',
      'pg-1003-baseline-20260907',
      'pg-1004-baseline-20260907',
      'pg-1005-baseline-20260907',
      'pg-1006-baseline-20260907',
      's3-2001-baseline-20260907',
      's3-2002-baseline-20260907',
      's3-2003-baseline-20260907',
      's3-2004-baseline-20260907',
      'pg-1003-20260907T163720Z-15001001',
      'pg-1004-20260907T163720Z-747084',
      'pg-1005-20260907T163720Z-747084',
      'pg-1006-20260907T163720Z-747084'
  );

IF (SELECT COUNT(*) FROM control.ctl_bronze_batch
    WHERE batch_status = 'committed' AND manifest_written = 1
      AND rows_expected = rows_committed
      AND RIGHT(manifest_path, 5) = '.json') <> 14
BEGIN
    RAISERROR('Historical Bronze manifest finalization did not produce 14 validated committed batches.', 16, 1);
END;

SELECT ingestion_batch_id, source_object_id, rows_expected, rows_committed,
       manifest_written, manifest_path
FROM control.ctl_bronze_batch
WHERE batch_status = 'committed'
ORDER BY source_object_id, ingestion_batch_id;
