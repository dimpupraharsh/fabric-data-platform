# Fabric notebook parameters. The build script places this block in a parameter cell.
bronze_workspace_id = "fba1bab2-0098-4b65-9f4f-cb304d71b700"
bronze_lakehouse_id = "ed2e34f8-b837-43c6-b6ba-de68cd7e0079"
bronze_target = ""
ingestion_batch_id = ""
# PARAMETERS_END

"""Add the snapshot lineage columns to one existing Bronze snapshot table.

This is a schema-only migration. It never reads or rewrites table rows. The
parent passes a target validated from the control warehouse, and the allow-list
below prevents an arbitrary table name from becoming executable SQL.
"""

import json
import re
from delta.tables import DeltaTable


allowed_targets = {
    "pg_customer_master",
    "pg_product_master",
    "s3_location_master",
    "s3_delivery_zone_lookup",
    "s3_warehouse_coverage",
    "s3_geo_hierarchy",
}

if bronze_target not in allowed_targets or not re.fullmatch(r"[a-z0-9_]+", bronze_target):
    raise ValueError(f"Target is not an approved small snapshot table: {bronze_target!r}")

# Refer to the attached Bronze Lakehouse explicitly; notebook default context
# can point at Silver when the same workspace hosts both Lakehouses.
table_path = (
    f"abfss://{bronze_workspace_id}@onelake.dfs.fabric.microsoft.com/"
    f"{bronze_lakehouse_id}/Tables/dbo/{bronze_target}"
)
source_df = spark.read.format("delta").load(table_path)
existing = set(source_df.columns)

# The Copy activity will populate these columns for every subsequent snapshot.
# Adding nullable fields preserves the already-ingested baseline as-is.
new_columns = {
    "dwh_ingest_run_id": "STRING",
    "dwh_source_object": "STRING",
    "dwh_ingest_ts": "TIMESTAMP",
    "dwh_ingest_batch_id": "STRING",
}
missing_columns = [(name, data_type) for name, data_type in new_columns.items() if name not in existing]
if missing_columns:
    definitions = ", ".join(f"`{name}` {data_type}" for name, data_type in missing_columns)
    spark.sql(f"ALTER TABLE delta.`{table_path}` ADD COLUMNS ({definitions})")

# If this same deterministic batch is replayed, remove only its partial rows
# before the next Copy attempt. Older batches and the baseline are untouched.
if ingestion_batch_id:
    DeltaTable.forPath(spark, table_path).delete(
        f"dwh_ingest_batch_id = '{ingestion_batch_id.replace(chr(39), chr(39) * 2)}'"
    )

final_columns = set(spark.read.format("delta").load(table_path).columns)
missing = sorted(set(new_columns) - final_columns)
if missing:
    raise RuntimeError(f"Bronze schema migration did not add expected columns: {missing}")

notebookutils.notebook.exit(json.dumps({
    "status": "succeeded",
    "bronze_target": bronze_target,
    "schema_only": True,
    "columns_added": [name for name, _ in missing_columns],
}))
