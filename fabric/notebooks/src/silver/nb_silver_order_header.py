# Fabric notebook parameters. The build script places this block in a parameter cell.
bronze_workspace_id = "fba1bab2-0098-4b65-9f4f-cb304d71b700"
bronze_lakehouse_id = "ed2e34f8-b837-43c6-b6ba-de68cd7e0079"
pipeline_run_id = "manual"
load_mode = "baseline"
lower_bound_ts = "1900-01-01T00:00:00Z"
# PARAMETERS_END

"""Conform complete-population order headers without confusing them with events.

The source order number is the business key. Latest Bronze source versions win;
status and date anomalies remain flagged for Gold eligibility decisions.
"""

import json
from delta.tables import DeltaTable
from pyspark.sql import Window
from pyspark.sql import functions as F

spark.conf.set("spark.sql.session.timeZone", "UTC")
spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
bronze_path = (
    f"abfss://{bronze_workspace_id}@onelake.dfs.fabric.microsoft.com/"
    f"{bronze_lakehouse_id}/Tables/dbo/pg_order_header"
)

# Processing is bounded by Bronze arrival, not order_date, so late corrections
# and historical status changes are not silently skipped.
source = spark.read.format("delta").load(bronze_path)
if load_mode == "incremental":
    source = source.filter(F.col("dwh_ingest_ts") > F.to_timestamp(F.lit(lower_bound_ts)))

version_rank = Window.partitionBy("order_number").orderBy(
    F.col("dwh_load_ts").desc_nulls_last(),
    F.col("dwh_ingest_ts").desc_nulls_last(),
    F.col("anchor_sales_key").desc(),
)
source = source.withColumn("_rank", F.row_number().over(version_rank)).filter("_rank = 1").drop("_rank")

# Keep the complete order state in Silver. A header status is current-state
# evidence; the three event facts remain sampled journey observations.
target = (
    source
    .withColumn("order_key", F.xxhash64(F.lit("retail_oi.order_header"), F.col("order_number")))
    .withColumn("order_date", F.to_date("order_date"))
    .withColumn("ship_date", F.to_date("ship_date"))
    .withColumn("due_date", F.to_date("due_date"))
    .withColumn("order_status", F.lower(F.trim("order_status")))
    .withColumn("shipment_status", F.lower(F.trim("shipment_status")))
    .withColumn("payment_status", F.lower(F.trim("payment_status")))
    .withColumn("dwh_order_status_valid", F.col("order_status").isin("created", "packed", "shipped", "delivered", "cancelled", "returned"))
    .withColumn("dwh_shipment_status_valid", F.col("shipment_status").isin("pending", "in_transit", "delayed", "delivered"))
    .withColumn("dwh_payment_status_valid", F.col("payment_status").isin("pending", "paid", "failed", "refunded"))
    .withColumn("dwh_due_date_valid", F.col("due_date").isNull() | (F.col("due_date") >= F.col("order_date")))
    .withColumn("dwh_delivery_date_valid", F.col("delivered_ts").isNull() | (F.to_date("delivered_ts") >= F.col("order_date")))
    .withColumn("dwh_source_load_ts", F.col("dwh_load_ts"))
    .withColumn("dwh_pipeline_run_id", F.lit(pipeline_run_id))
    .withColumn("dwh_silver_load_ts", F.current_timestamp())
    .withColumn("dwh_record_hash", F.sha2(F.concat_ws("||", "order_number", "customer_id", "order_date", "order_status", "shipment_status", "payment_status", "delivered_ts"), 256))
    .drop("dwh_load_ts")
)

table_name = "conformed.fact_order"
changed_rows = target.count()
invalid_rows = target.filter(
    ~F.col("dwh_order_status_valid") | ~F.col("dwh_shipment_status_valid") |
    ~F.col("dwh_payment_status_valid") | ~F.col("dwh_due_date_valid") |
    ~F.col("dwh_delivery_date_valid")
).count()
if spark.catalog.tableExists(table_name):
    (
        DeltaTable.forName(spark, table_name).alias("t")
        .merge(target.alias("s"), "t.order_number = s.order_number")
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
else:
    target.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table_name)

notebookutils.notebook.exit(json.dumps({
    "status": "succeeded", "pipeline_run_id": pipeline_run_id,
    "load_mode": load_mode, "rows_read": changed_rows,
    "invalid_status_or_date_rows": invalid_rows,
    "target": table_name,
}))
