# Fabric notebook parameters. The build script places this block in a parameter cell.
bronze_workspace_id = "fba1bab2-0098-4b65-9f4f-cb304d71b700"
bronze_lakehouse_id = "ed2e34f8-b837-43c6-b6ba-de68cd7e0079"
pipeline_run_id = "manual"
load_mode = "baseline"
lower_bound_ts = "1900-01-01T00:00:00Z"
# PARAMETERS_END

"""Conform operational event streams into three Silver event facts.

The source event key is retained for idempotent merges. Business event time
drives lifecycle ordering; Bronze arrival time remains separate for late-data
measurement. This notebook does not discard invalid statuses silently.
"""

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
import json

spark.conf.set("spark.sql.session.timeZone", "UTC")
spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
BRONZE_ROOT = (
    f"abfss://{bronze_workspace_id}@onelake.dfs.fabric.microsoft.com/"
    f"{bronze_lakehouse_id}/Tables/dbo"
)


def bronze(table_name: str) -> DataFrame:
    """Read one event stream from the configured Bronze Lakehouse."""
    return spark.read.format("delta").load(f"{BRONZE_ROOT}/{table_name}")


def merge_table(df: DataFrame, table_name: str) -> None:
    """Merge event versions by immutable source event key, or create the target.

    Args:
        df: Prepared event rows for one source stream.
        table_name: Fully qualified Silver event fact table.
    Returns:
        None. Existing event keys are updated; unseen keys are inserted.
    """
    # Merge by the immutable source event identifier so pipeline retries are
    # updates to the same event, not additional event rows.
    if spark.catalog.tableExists(table_name):
        (
            DeltaTable.forName(spark, table_name).alias("t")
            .merge(df.alias("s"), "t.source_event_key = s.source_event_key")
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )
    else:
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table_name)


def build_event(source_table: str, target_table: str, status_column: str, allowed_statuses: list[str]) -> dict:
    """Conform one source event table and return a compact run summary.

    Args:
        source_table: Bronze table name for one order/shipment/payment stream.
        target_table: Silver fact table to merge.
        status_column: Source-specific status attribute to normalize.
        allowed_statuses: Approved lowercase values used to flag bad statuses.
    Returns:
        Counts and target/source names for the parent pipeline's run output.
    """
    # The arrival boundary makes routine processing incremental while keeping
    # event_ts available for business ordering and late-arrival measurement.
    source = bronze(source_table)
    if load_mode == "incremental":
        source = source.filter(F.col("dwh_ingest_ts") > F.to_timestamp(F.lit(lower_bound_ts)))
    window = Window.partitionBy("event_key").orderBy(
        F.col("dwh_load_ts").desc_nulls_last(),
        F.col("dwh_ingest_ts").desc_nulls_last(),
        F.col("dwh_ingest_batch_id").desc_nulls_last(),
    )
    source = source.withColumn("_rn", F.row_number().over(window)).filter("_rn = 1").drop("_rn")
    # Normalize only Silver's status representation; source-shaped Bronze is
    # immutable and retains the original status text for lineage/audit.
    normalized_status = F.lower(F.trim(F.col(status_column)))
    target = (
        source
        .withColumn("source_event_key", F.col("event_key").cast("long"))
        .withColumn("event_key", F.xxhash64(F.lit(source_table), F.col("event_key").cast("string")))
        .withColumn("event_status", normalized_status)
        .withColumn("event_ts", F.to_timestamp("event_ts"))
        .withColumn("dwh_status_valid", normalized_status.isin(allowed_statuses))
        .withColumn("dwh_arrival_delay_seconds", F.unix_timestamp(F.coalesce("dwh_ingest_ts", "dwh_load_ts")) - F.unix_timestamp("event_ts"))
        .withColumn("dwh_source_load_ts", F.col("dwh_load_ts"))
        .withColumn("dwh_pipeline_run_id", F.lit(pipeline_run_id))
        .withColumn("dwh_silver_load_ts", F.current_timestamp())
        .withColumn("dwh_record_hash", F.sha2(F.concat_ws("||", "order_number", normalized_status, F.col("event_ts").cast("string")), 256))
        # Shipment/payment have source-specific status names to remove. Order
        # already calls its source column event_status, so dropping that name
        # would also drop the conformed value we just created.
        .drop(*([status_column] if status_column != "event_status" else []), "dwh_load_ts")
    )
    merge_table(target, target_table)
    return {
        "source": source_table,
        "target": target_table,
        "rows_read": source.count(),
        "invalid_status_rows": target.filter(~F.col("dwh_status_valid")).count(),
    }


# Process each lifecycle domain through the same tested merge pattern while
# keeping its own status vocabulary and Silver target independent.
results = [
    build_event("pg_order_status_event", "conformed.fact_order_event", "event_status", ["created", "packed", "shipped", "delivered", "cancelled", "returned"]),
    build_event("pg_shipment_status_event", "conformed.fact_shipment_event", "shipment_status", ["pending", "in_transit", "delayed", "delivered"]),
    build_event("pg_payment_status_event", "conformed.fact_payment_event", "payment_status", ["pending", "paid", "failed", "refunded"]),
]
notebookutils.notebook.exit(json.dumps({"status": "succeeded", "pipeline_run_id": pipeline_run_id, "load_mode": load_mode, "objects": results}))
