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

# # Silver Reconciliation
# 
# Checks Silver sales/order key uniqueness, source balances, complete order-header coverage, approved statuses, SCD current-row rules, dimension references, and event uniqueness; hard failures block commit.
# 
# ## What this notebook reads and writes
# 
# **Inputs:** the Silver facts/dimensions/rejects plus Bronze sales source keys. **Output:** append-only check results in `ops.reconciliation_result`; the notebook also returns a machine-readable summary to the parent.
# 
# **Checks:** one accepted sales row per source key; accepted plus hard rejects equals distinct Bronze source sales keys; one current SCD version per entity; required customer/product references resolve; and each event fact is unique by source event key. Any failed hard check raises an exception so the parent cannot mark the Silver run successful.
# 
# **Parameters:** `pipeline_run_id`, `load_mode`, `bronze_workspace_id`, and `bronze_lakehouse_id` identify the run and the source table used for reconciliation.


# PARAMETERS CELL ********************

bronze_workspace_id = "fba1bab2-0098-4b65-9f4f-cb304d71b700"
bronze_lakehouse_id = "ed2e34f8-b837-43c6-b6ba-de68cd7e0079"
pipeline_run_id = "manual"
load_mode = "baseline"


# CELL ********************

"""Validate Silver invariants before the parent pipeline commits success.

Checks cover source-key uniqueness, accepted/rejected balance, exactly one
current dimension version, complete fact foreign keys, and event uniqueness.
Any failed hard check raises an error so the orchestration run cannot commit.
"""

from pyspark.sql import functions as F
import json

BRONZE_ROOT = (
    f"abfss://{bronze_workspace_id}@onelake.dfs.fabric.microsoft.com/"
    f"{bronze_lakehouse_id}/Tables/dbo"
)

# Store machine-readable check outcomes in Silver ops for auditable reruns.
checks = []


def add_check(name: str, observed: int, expected: int | None, passed: bool, detail: str) -> None:
    """Append one named assertion to the report returned to the pipeline.

    Args:
        name: Stable check identifier suitable for monitoring and alert rules.
        observed: Actual count/value measured in Silver or Bronze.
        expected: Expected value, or None when the check is a boolean invariant.
        passed: Whether the observed result satisfies the invariant.
        detail: Plain-language meaning of the check for operators.
    Returns:
        None. The shared `checks` collection is written after all checks run.
    """
    checks.append({
        "check_name": name,
        "observed_value": int(observed),
        "expected_value": None if expected is None else int(expected),
        "passed": bool(passed),
        "detail": detail,
    })


# Reconcile against the complete Bronze business-key population, not a guessed
# scale constant, so future scale changes do not require code edits.
fact_sales = spark.table("conformed.fact_sales")
fact_order = spark.table("conformed.fact_order")
dq_rejects = spark.table("quality.dq_rejects")
dim_customer = spark.table("conformed.dim_customer")
dim_product = spark.table("conformed.dim_product")
dim_location = spark.table("conformed.dim_location")

fact_count = fact_sales.count()
reject_count = dq_rejects.filter("source_object = 'pg_sales_order_line'").count()
expected_sales_source_rows = (
    spark.read.format("delta").load(f"{BRONZE_ROOT}/pg_sales_order_line")
    .select("sales_key").distinct().count()
)
distinct_sales = fact_sales.select("source_sales_key").distinct().count()
add_check("fact_sales_unique_source_key", fact_count - distinct_sales, 0, fact_count == distinct_sales, "No duplicate accepted source sales keys")
add_check(
    "sales_accept_reject_reconciliation",
    fact_count + reject_count,
    expected_sales_source_rows,
    fact_count + reject_count == expected_sales_source_rows,
    "Accepted plus hard rejects equals current Bronze source-key count",
)

# Each historized entity may have exactly one open/current version. The
# explicit unknown location member is excluded from this entity-level test.
for name, frame, entity_key in (
    ("dim_customer", dim_customer, "customer_entity_key"),
    ("dim_product", dim_product, "product_entity_key"),
    ("dim_location", dim_location.filter("location_entity_key <> 0"), "location_entity_key"),
):
    duplicate_current = (
        frame.filter("dwh_is_current = true")
        .groupBy(entity_key).count().filter("count <> 1").count()
    )
    add_check(f"{name}_one_current_version", duplicate_current, 0, duplicate_current == 0, "Exactly one current version per entity")

missing_customer_keys = fact_sales.filter("customer_key is null").count()
missing_product_keys = fact_sales.filter("product_key is null").count()
add_check("fact_sales_customer_key_complete", missing_customer_keys, 0, missing_customer_keys == 0, "All accepted facts resolve customer as of order date")
add_check("fact_sales_product_key_complete", missing_product_keys, 0, missing_product_keys == 0, "All accepted facts resolve product as of order date")

# Order headers provide the complete-population denominator. The event facts
# are sampled and must not be used as a substitute for this source count.
order_count = fact_order.count()
unique_orders = fact_order.select("order_number").distinct().count()
source_order_count = (
    spark.read.format("delta").load(f"{BRONZE_ROOT}/pg_order_header")
    .select("order_number").distinct().count()
)
add_check("fact_order_unique_number", order_count - unique_orders, 0, order_count == unique_orders, "One conformed header per business order number")
add_check("order_header_source_reconciliation", order_count, source_order_count, order_count == source_order_count, "All Bronze order headers resolve to one Silver order")
invalid_order_statuses = fact_order.filter(
    "NOT dwh_order_status_valid OR NOT dwh_shipment_status_valid OR NOT dwh_payment_status_valid"
).count()
add_check("fact_order_status_vocabulary", invalid_order_statuses, 0, invalid_order_statuses == 0, "Every complete-population order state uses approved status values")
missing_order_headers = (
    fact_sales.select("order_number").distinct()
    .join(fact_order.select("order_number"), "order_number", "left_anti")
    .count()
)
add_check("sales_order_header_coverage", missing_order_headers, 0, missing_order_headers == 0, "Every accepted sales order number has a conformed header")

# Event facts use immutable source event IDs, so retries must not increase the
# number of distinct event records.
event_counts = {}
for table_name in ("fact_order_event", "fact_shipment_event", "fact_payment_event"):
    frame = spark.table(f"conformed.{table_name}")
    count = frame.count()
    duplicates = count - frame.select("source_event_key").distinct().count()
    event_counts[table_name] = count
    add_check(f"{table_name}_unique_source_key", duplicates, 0, duplicates == 0, "No duplicate source event keys")

warning_rows = fact_sales.filter("dwh_dq_status = 'warning'").count()
inferred_product_versions = dim_product.filter("dwh_is_inferred = true").count()
failed_checks = [check for check in checks if not check["passed"]]

# Persist every check, including passes, so operators can compare runs rather
# than seeing only failures in the pipeline output.
rows = [(
    pipeline_run_id,
    load_mode,
    check["check_name"],
    check["observed_value"],
    check["expected_value"],
    check["passed"],
    check["detail"],
) for check in checks]
result_df = spark.createDataFrame(
    rows,
    "pipeline_run_id string, load_mode string, check_name string, observed_value long, expected_value long, passed boolean, detail string",
).withColumn("checked_ts", F.current_timestamp())
result_df.write.format("delta").mode("append").saveAsTable("ops.reconciliation_result")

result = {
    "status": "failed" if failed_checks else "succeeded",
    "pipeline_run_id": pipeline_run_id,
    "load_mode": load_mode,
    "fact_sales_rows": fact_count,
    "sales_reject_rows": reject_count,
    "warning_rows": warning_rows,
    "inferred_product_versions": inferred_product_versions,
    "event_counts": event_counts,
    "failed_checks": failed_checks,
}
if failed_checks:
    raise RuntimeError(json.dumps(result))
notebookutils.notebook.exit(json.dumps(result))

