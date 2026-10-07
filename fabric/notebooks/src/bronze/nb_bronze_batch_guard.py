# Fabric notebook parameters. The build script places this block in a parameter cell.
operation = "inspect_batch"
bronze_target = "pg_sales_order_line"
ingestion_batch_id = ""
source_object_id = "1003"
source_object_name = "retail_oi.sales_order_line"
pipeline_run_id = ""
lower_watermark = ""
upper_watermark = ""
lower_tie_breaker = "0"
upper_tie_breaker = "0"
rows_expected = "0"
manifest_relative_path = "Files/manifests/postgresql/sales_order_line/batch.json"
manifest_specs_json = "[]"
# PARAMETERS_END

import json
from datetime import datetime, timezone
from notebookutils import mssparkutils
from pyspark.sql import functions as F
from pyspark.sql import types as T
from delta.tables import DeltaTable

WORKSPACE_ID = "fba1bab2-0098-4b65-9f4f-cb304d71b700"
LAKEHOUSE_NAME = "lh_retail_bronze"
TABLES = [
    "pg_customer_master", "pg_product_master", "pg_sales_order_line",
    "pg_order_header",
    "pg_order_status_event", "pg_shipment_status_event",
    "pg_payment_status_event", "s3_location_master",
    "s3_delivery_zone_lookup", "s3_warehouse_coverage",
    "s3_geo_hierarchy",
]
TECHNICAL_COLUMNS = [
    ("dwh_ingest_run_id", "STRING"),
    ("dwh_source_object", "STRING"),
    ("dwh_ingest_ts", "TIMESTAMP"),
    ("dwh_ingest_batch_id", "STRING"),
]

# Only registered Bronze objects are allowed, which limits the effect of metadata mistakes.
def table_path(name):
    """Return a relative Delta-table path for one allow-listed Bronze target.

    Args:
        name: Registered table name from the Bronze pipeline contract.
    Returns:
        A `Tables/dbo/<name>` path safe to pass to Spark Delta readers.
    Raises:
        ValueError: If metadata supplies a table outside the approved inventory.
    """
    if name not in TABLES:
        raise ValueError(f"Unapproved Bronze target: {name}")
    return f"Tables/dbo/{name}"


def ensure_order_header_target(name):
    """Create only the approved new order-header target before first replay.

    Args:
        name: Allow-listed Bronze table name supplied by the pipeline.
    Returns:
        None. Existing Delta tables are never overwritten or altered here.
    """
    if name != "pg_order_header":
        return
    if spark.catalog.tableExists("dbo.pg_order_header"):
        existing = spark.table("dbo.pg_order_header")
        # Fabric Copy maps PostgreSQL DATE to DateTime. Repair only the empty
        # target from the failed first attempt; never rewrite landed rows.
        if isinstance(existing.schema["order_date"].dataType, T.TimestampType):
            return
        if existing.count() != 0:
            raise RuntimeError("pg_order_header has rows with an incompatible date schema")
        spark.sql("DROP TABLE dbo.pg_order_header")
    schema = T.StructType([
        T.StructField("order_number", T.StringType()),
        T.StructField("anchor_sales_key", T.LongType()),
        T.StructField("customer_id", T.IntegerType()),
        T.StructField("order_date", T.TimestampType()),
        T.StructField("ship_date", T.TimestampType()),
        T.StructField("due_date", T.TimestampType()),
        T.StructField("dwh_load_ts", T.TimestampType()),
        T.StructField("dwh_source_system", T.StringType()),
        T.StructField("order_status", T.StringType()),
        T.StructField("shipment_status", T.StringType()),
        T.StructField("payment_status", T.StringType()),
        T.StructField("delivered_ts", T.TimestampType()),
        T.StructField("payment_ts", T.TimestampType()),
        T.StructField("status_updated_ts", T.TimestampType()),
        T.StructField("dwh_ingest_run_id", T.StringType()),
        T.StructField("dwh_source_object", T.StringType()),
        T.StructField("dwh_ingest_ts", T.TimestampType()),
        T.StructField("dwh_ingest_batch_id", T.StringType()),
    ])
    spark.createDataFrame([], schema).write.format("delta").mode("errorifexists").saveAsTable("dbo.pg_order_header")

# Keep manifest writes under the approved landing folder and reject unsafe paths.
def manifest_path(relative_path):
    """Validate and normalize a manifest path under the Bronze manifests folder.

    Args:
        relative_path: Pipeline-supplied path, relative to the Lakehouse root.
    Returns:
        A normalized `Files/manifests/...json` path.
    Raises:
        ValueError: If the path escapes the manifest folder or is not JSON.
    """
    clean = relative_path.lstrip("/")
    if not clean.startswith("Files/manifests/") or not clean.endswith(".json"):
        raise ValueError(f"Invalid manifest path: {relative_path}")
    return clean

# Count rows tagged with this batch ID so an exact replay can be detected.
def batch_count(name, batch_id):
    """Count Bronze rows written by exactly one ingestion batch.

    Args:
        name: Allow-listed Bronze table name.
        batch_id: Deterministic run/object batch identity.
    Returns:
        Number of rows carrying that batch ID; zero when no batch ID exists.
    """
    if not batch_id:
        return 0
    ensure_order_header_target(name)
    frame = spark.read.format("delta").load(table_path(name))
    if "dwh_ingest_batch_id" not in frame.columns:
        return 0
    return frame.where(F.col("dwh_ingest_batch_id") == batch_id).count()

# A manifest is immutable: a repeated write must agree with the committed batch.
def write_immutable_manifest(relative_path, payload):
    """Create a manifest once, or verify that a replay matches the receipt.

    Args:
        relative_path: Approved manifest destination inside the Lakehouse.
        payload: JSON-serializable row counts, keys, run IDs, and bounds.
    Returns:
        None. A conflicting existing receipt raises an error; it is never replaced.
    """
    output_path = manifest_path(relative_path)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    mssparkutils.fs.mkdirs(output_path.rsplit("/", 1)[0])
    if mssparkutils.fs.exists(output_path):
        prior_payload = json.loads(mssparkutils.fs.head(output_path, 1024 * 1024))
        for field in ["ingestion_batch_id", "source_object_id", "bronze_target", "rows_committed"]:
            if prior_payload.get(field) != payload.get(field):
                raise RuntimeError(f"Manifest replay conflict for {field}")
    else:
        mssparkutils.fs.put(output_path, serialized, False)

def historical_count(spec):
    """Count rows in a historical snapshot or bounded watermark interval.

    Args:
        spec: Object metadata containing target, watermark/key columns, and bounds.
    Returns:
        Number of Bronze rows in the requested full-table or bounded range.
    """
    frame = spark.read.format("delta").load(table_path(spec["bronze_target"]))
    if spec.get("count_mode") == "full_table":
        return frame.count()
    watermark = F.col(spec["watermark_column"])
    tie_breaker = F.col(spec["tie_breaker_column"]).cast("long")
    upper_ts = F.to_timestamp(F.lit(spec["upper_watermark"]))
    upper_tie = F.lit(int(spec["upper_tie_breaker"]))
    predicate = (watermark < upper_ts) | ((watermark == upper_ts) & (tie_breaker <= upper_tie))
    if spec.get("lower_watermark"):
        lower_ts = F.to_timestamp(F.lit(spec["lower_watermark"]))
        lower_tie = F.lit(int(spec["lower_tie_breaker"]))
        predicate = predicate & ((watermark > lower_ts) | ((watermark == lower_ts) & (tie_breaker > lower_tie)))
    return frame.where(predicate).count()

# Select one controlled operation. Each branch returns a small result payload
# for the calling pipeline; unknown operation names fail closed.
if operation == "prepare_tables":
    changed = []
    for name in TABLES:
        ensure_order_header_target(name)
        path = table_path(name)
        existing = set(spark.read.format("delta").load(path).columns)
        missing = [(column, data_type) for column, data_type in TECHNICAL_COLUMNS if column not in existing]
        if missing:
            definition = ", ".join(f"{column} {data_type}" for column, data_type in missing)
            spark.sql(f"ALTER TABLE delta.`{path}` ADD COLUMNS ({definition})")
            changed.append({"table": name, "columns_added": [column for column, _ in missing]})
    result = {"status": "prepared", "changed": changed, "table_count": len(TABLES)}
elif operation == "inspect_batch":
    observed = batch_count(bronze_target, ingestion_batch_id)
    result = {"status": "inspected", "rows_observed": observed, "batch_exists": observed > 0}
elif operation == "reset_staged_batch":
    prior = batch_count(bronze_target, ingestion_batch_id)
    if prior > 0:
        DeltaTable.forPath(spark, table_path(bronze_target)).delete(F.col("dwh_ingest_batch_id") == ingestion_batch_id)
    result = {"status": "reset", "rows_removed": prior, "ingestion_batch_id": ingestion_batch_id}
elif operation == "backfill_manifests":
    written = []
    for spec in json.loads(manifest_specs_json):
        observed = historical_count(spec)
        expected = int(spec["rows_expected"])
        if observed != expected:
            raise RuntimeError(f"Historical Bronze count mismatch for {spec['ingestion_batch_id']}: expected={expected}, observed={observed}")
        path = spec["manifest_path"]
        if not path.endswith(".json"):
            path = f"{path}/{spec['ingestion_batch_id']}.json"
        payload = {
            "manifest_version": 1, "ingestion_batch_id": spec["ingestion_batch_id"],
            "pipeline_run_id": spec["pipeline_run_id"], "source_object_id": int(spec["source_object_id"]),
            "source_object_name": spec["source_object_name"], "bronze_target": spec["bronze_target"],
            "lower_watermark": spec.get("lower_watermark"), "upper_watermark": spec.get("upper_watermark"),
            "lower_tie_breaker": spec.get("lower_tie_breaker"), "upper_tie_breaker": spec.get("upper_tie_breaker"),
            "rows_expected": expected, "rows_committed": observed,
            "created_utc": datetime.now(timezone.utc).isoformat(), "historical_backfill": True,
        }
        write_immutable_manifest(path, payload)
        written.append({"ingestion_batch_id": spec["ingestion_batch_id"], "rows_observed": observed, "manifest_path": path})
    result = {"status": "backfilled", "manifest_count": len(written), "manifests": written}
elif operation == "validate_and_manifest":
    expected = int(rows_expected)
    observed = batch_count(bronze_target, ingestion_batch_id)
    if observed != expected:
        raise RuntimeError(f"Bronze batch count mismatch: expected={expected}, observed={observed}")
    payload = {
        "manifest_version": 1,
        "ingestion_batch_id": ingestion_batch_id,
        "pipeline_run_id": pipeline_run_id,
        "source_object_id": int(source_object_id),
        "source_object_name": source_object_name,
        "bronze_target": bronze_target,
        "lower_watermark": lower_watermark or None,
        "upper_watermark": upper_watermark or None,
        "lower_tie_breaker": lower_tie_breaker or None,
        "upper_tie_breaker": upper_tie_breaker or None,
        "rows_expected": expected,
        "rows_committed": observed,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_immutable_manifest(manifest_relative_path, payload)
    result = {"status": "validated", "rows_observed": observed, "manifest_written": True, "manifest_path": manifest_relative_path}
else:
    raise ValueError(f"Unsupported operation: {operation}")

mssparkutils.notebook.exit(json.dumps(result, separators=(",", ":")))
