# Fabric notebook source

# METADATA ********************

# META {
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "008a8245-d6ca-42fb-bd45-17e1dfef0835",
# META       "default_lakehouse_name": "lh_retail_silver",
# META       "default_lakehouse_workspace_id": "fba1bab2-0098-4b65-9f4f-cb304d71b700",
# META       "known_lakehouses": [
# META         {
# META           "id": "008a8245-d6ca-42fb-bd45-17e1dfef0835"
# META         },
# META         {
# META           "id": "ed2e34f8-b837-43c6-b6ba-de68cd7e0079"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Silver Sales
# 
# Builds the line-item sales fact, resolves SCD dimension versions as of order date, flags soft data defects, rejects hard reference failures, and merges on source sales key.
# 
# ## What this notebook reads and writes
# 
# **Inputs:** Bronze `pg_sales_order_line` plus the conformed customer, product, and location dimensions. **Outputs:** `conformed.fact_sales` and `quality.dq_rejects`. Grain is one product line on one order.
# 
# **How it works:** incremental mode filters by Bronze arrival time; the newest version per `sales_key` wins; types and rule flags are calculated; each line resolves dimension versions valid on `order_date`; hard missing-key failures are written to rejects; soft date/arithmetic defects remain accepted with warning flags; and Delta merge by source sales key prevents duplicate facts.
# 
# **Parameters:** `pipeline_run_id`, `load_mode`, and `lower_bound_ts` come from the parent pipeline. Baseline is for a deliberate rebuild only. The result reports rows read, accepted, rejected, and warned.


# PARAMETERS CELL ********************

bronze_workspace_id = "fba1bab2-0098-4b65-9f4f-cb304d71b700"
bronze_lakehouse_id = "ed2e34f8-b837-43c6-b6ba-de68cd7e0079"
pipeline_run_id = "manual"
load_mode = "baseline"
lower_bound_ts = "1900-01-01T00:00:00Z"


# CELL ********************

"""Build the line-item sales fact with as-of dimension resolution.

Each source sales key represents one product line on one order. The joins use
the dimension version valid on order_date, not merely today's current row.
Business-rule defects remain visible as warning flags; missing required keys
are hard rejects and are not allowed to disappear from reconciliation.
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
    """Read a Bronze Delta table by its registered table name."""
    return spark.read.format("delta").load(f"{BRONZE_ROOT}/{table_name}")


def record_hash(*columns):
    """Build a stable hash from the fact values used to detect row changes."""
    return F.sha2(
        F.concat_ws("||", *[F.coalesce(c.cast("string"), F.lit("<null>")) for c in columns]),
        256,
    )


def merge_table(df: DataFrame, table_name: str, match_condition: str, partition_columns=None) -> None:
    """Write a baseline output or idempotently merge incremental fact rows.

    Args:
        df: Accepted fact records for this execution window.
        table_name: Silver Delta target table.
        match_condition: Delta SQL predicate matching target and source records.
        partition_columns: Optional partition columns used for first creation.
    Returns:
        None. Baseline overwrites this Silver target; incremental mode merges it.
    """
    # Baseline is a deliberate initial build; incremental reruns merge by the
    # stable source key to make replay safe.
    if load_mode == "baseline":
        writer = df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
        if partition_columns:
            writer = writer.partitionBy(*partition_columns)
        writer.saveAsTable(table_name)
        return
    if spark.catalog.tableExists(table_name):
        target = DeltaTable.forName(spark, table_name)
        (
            target.alias("t")
            .merge(df.alias("s"), match_condition)
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )
    else:
        writer = df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
        if partition_columns:
            writer = writer.partitionBy(*partition_columns)
        writer.saveAsTable(table_name)


# Read raw line items. Arrival time chooses which rows to reconsider; order_date
# later chooses which historical dimension versions each line receives.
sales_raw = bronze("pg_sales_order_line")
if load_mode == "incremental":
    sales_raw = sales_raw.filter(F.col("dwh_ingest_ts") > F.to_timestamp(F.lit(lower_bound_ts)))

# Bronze is append-history: updates arrive as another version of the same
# sales_key. Select one deterministic latest version before shaping the fact.
latest_window = Window.partitionBy("sales_key").orderBy(
    F.col("dwh_load_ts").desc_nulls_last(),
    F.col("dwh_ingest_ts").desc_nulls_last(),
    F.col("dwh_ingest_batch_id").desc_nulls_last(),
)
sales = sales_raw.withColumn("_rn", F.row_number().over(latest_window)).filter("_rn = 1").drop("_rn")

# Cast the source contract into analytic types and retain rule-level flags.
# Soft defects stay visible instead of being silently removed from the fact.
sales = (
    sales
    .withColumn("source_sales_key", F.col("sales_key").cast("long"))
    .withColumn("sales_key", F.xxhash64(F.lit("postgresql"), F.col("sales_key").cast("string")))
    .withColumn("order_date", F.to_date("order_date"))
    .withColumn("ship_date", F.to_date("ship_date"))
    .withColumn("due_date", F.to_date("due_date"))
    .withColumn("sales_amount", F.col("sales_amount").cast("decimal(18,2)"))
    .withColumn("quantity", F.col("quantity").cast("int"))
    .withColumn("unit_price", F.col("unit_price").cast("decimal(18,2)"))
    .withColumn("dq_ship_before_order", F.col("ship_date").isNotNull() & (F.col("ship_date") < F.col("order_date")))
    .withColumn("dq_due_before_order", F.col("due_date").isNotNull() & (F.col("due_date") < F.col("order_date")))
    .withColumn(
        "dq_sales_amount_mismatch",
        F.abs(F.col("sales_amount") - (F.col("quantity") * F.col("unit_price"))) > F.lit(0.01),
    )
    .withColumn(
        "dwh_dq_status",
        F.when(
            F.col("dq_ship_before_order") | F.col("dq_due_before_order") | F.col("dq_sales_amount_mismatch"),
            F.lit("warning"),
        ).otherwise(F.lit("passed")),
    )
)

# Pull effective intervals so each sale resolves to the historically correct
# customer and product version for the order date.
customers = spark.table("conformed.dim_customer").select(
    "customer_key", "customer_entity_key", "customer_id", "location_entity_key",
    F.col("dwh_effective_from").alias("customer_effective_from"),
    F.col("dwh_effective_to").alias("customer_effective_to"),
)
products = spark.table("conformed.dim_product").select(
    "product_key", "product_entity_key", "product_business_key", "category_key",
    F.col("dwh_effective_from").alias("product_effective_from"),
    F.col("dwh_effective_to").alias("product_effective_to"),
)
locations = spark.table("conformed.dim_location").select(
    "location_key", "location_entity_key",
    F.col("dwh_effective_from").alias("location_effective_from"),
    F.col("dwh_effective_to").alias("location_effective_to"),
)

# These are temporal joins: a transaction uses the dimension version valid on
# its business date, not today's current customer/product/location attributes.
fact_stage = (
    sales.alias("s")
    .join(
        customers.alias("c"),
        (F.col("s.customer_id") == F.col("c.customer_id"))
        & (F.to_timestamp("s.order_date") >= F.col("c.customer_effective_from"))
        & (F.to_timestamp("s.order_date") < F.col("c.customer_effective_to")),
        "left",
    )
    .join(
        products.alias("p"),
        (F.col("s.product_business_key") == F.col("p.product_business_key"))
        & (F.to_timestamp("s.order_date") >= F.col("p.product_effective_from"))
        & (F.to_timestamp("s.order_date") < F.col("p.product_effective_to")),
        "left",
    )
    .join(
        locations.alias("l"),
        (F.col("c.location_entity_key") == F.col("l.location_entity_key"))
        & (F.to_timestamp("s.order_date") >= F.col("l.location_effective_from"))
        & (F.to_timestamp("s.order_date") < F.col("l.location_effective_to")),
        "left",
    )
)

# A missing required business key is a reject; date/arithmetic defects below
# remain accepted with warning flags for analysis and learning.
hard_reject_condition = (
    F.col("s.source_sales_key").isNull()
    | F.col("s.order_number").isNull()
    | F.col("s.order_date").isNull()
    | F.col("c.customer_key").isNull()
    | F.col("p.product_key").isNull()
)

# Hard key/reference failures cannot support trustworthy dimensional analysis;
# keep their raw payload and source identity in the reject table for repair.
rejects = (
    fact_stage.filter(hard_reject_condition)
    .select(
        F.sha2(F.concat_ws("||", F.lit("pg_sales_order_line"), F.col("s.source_sales_key"), F.lit("missing_required_reference")), 256).alias("reject_key"),
        F.lit("pg_sales_order_line").alias("source_object"),
        F.col("s.source_sales_key").cast("string").alias("source_record_key"),
        F.lit("missing_required_reference").alias("rule_code"),
        F.lit("error").alias("severity"),
        F.when(F.col("c.customer_key").isNull(), F.lit("customer"))
        .when(F.col("p.product_key").isNull(), F.lit("product"))
        .otherwise(F.lit("required_key")).alias("observed_value"),
        F.to_json(F.struct(F.col("s.*"))).alias("raw_record_payload"),
        F.col("s.dwh_ingest_batch_id").alias("dwh_bronze_batch_id"),
        F.lit(pipeline_run_id).alias("dwh_pipeline_run_id"),
        F.current_timestamp().alias("dwh_rejected_ts"),
    )
)

# Keep accepted records at source line-item grain and preserve keys/lineage so
# totals reconcile to Bronze and a late correction can update one target row.
accepted = (
    fact_stage.filter(~hard_reject_condition)
    .select(
        F.col("s.sales_key"), F.col("s.source_sales_key"), F.col("s.order_number"),
        F.col("c.customer_key"), F.col("c.customer_entity_key"),
        F.col("p.product_key"), F.col("p.product_entity_key"), F.col("p.category_key"),
        F.coalesce(F.col("l.location_key"), F.lit(0).cast("long")).alias("location_key"),
        F.col("c.location_entity_key"), F.col("s.product_business_key"), F.col("s.customer_id"),
        F.col("s.order_date"), F.col("s.ship_date"), F.col("s.due_date"),
        F.col("s.sales_amount"), F.col("s.quantity"), F.col("s.unit_price"),
        F.col("s.dq_ship_before_order"), F.col("s.dq_due_before_order"),
        F.col("s.dq_sales_amount_mismatch"), F.col("s.dwh_dq_status"),
        F.year("s.order_date").alias("order_year"),
        F.col("s.dwh_load_ts").alias("dwh_source_load_ts"),
        F.col("s.dwh_source_system"), F.col("s.dwh_ingest_run_id"),
        F.col("s.dwh_ingest_batch_id"), F.col("s.dwh_ingest_ts"),
        F.lit(pipeline_run_id).alias("dwh_pipeline_run_id"),
        F.current_timestamp().alias("dwh_silver_load_ts"),
    )
    .withColumn("dwh_record_hash", record_hash(
        F.col("source_sales_key"), F.col("customer_key"), F.col("product_key"),
        F.col("location_key"), F.col("ship_date"), F.col("due_date"),
        F.col("sales_amount"), F.col("quantity"), F.col("unit_price"),
    ))
)

merge_table(accepted, "conformed.fact_sales", "t.source_sales_key = s.source_sales_key", ["order_year"])
merge_table(rejects, "quality.dq_rejects", "t.reject_key = s.reject_key")

result = {
    "status": "succeeded",
    "pipeline_run_id": pipeline_run_id,
    "load_mode": load_mode,
    "rows_read": sales.count(),
    "rows_accepted": accepted.count(),
    "rows_rejected": rejects.count(),
    "warning_rows": accepted.filter("dwh_dq_status = 'warning'").count(),
}
notebookutils.notebook.exit(json.dumps(result))

