"""Fabric Spark fixture: bounded, isolated transformation acceptance tests.

The controller supplies WORKSPACE_ID, BRONZE_ID and TRANSFORM_SOURCES. All writes
stay in dedicated acceptance Lakehouses in Test. No source credentials or source
system writes are involved. Test evidence remains available for debugging.
"""

import ast
from decimal import Decimal
import hashlib
import json

from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

spark.conf.set("spark.sql.session.timeZone", "UTC")
ROOT = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_ID}"
OWNER = "retail_ci_business_fixture_v1"
TIMES = {"baseline": "2025-01-01 00:00:00", "incremental": "2025-03-01 00:00:00"}


def frame(rows, phase, null_arrival=False):
    """Create explicitly typed source-shaped rows, including Bronze lineage."""
    enriched = [{**row, "dwh_source_system": "acceptance_fixture",
                 "dwh_load_ts": TIMES[phase],
                 "dwh_ingest_ts": None if null_arrival else TIMES[phase],
                 "dwh_ingest_run_id": OWNER, "dwh_ingest_batch_id": phase} for row in rows]
    columns = sorted(set().union(*(row.keys() for row in enriched)))
    schema = StructType([StructField(name, StringType(), True) for name in columns])
    df = spark.createDataFrame([[None if row.get(name) is None else str(row[name])
                                 for name in columns] for row in enriched], schema)
    for name in columns:
        if name in ("dwh_load_ts", "dwh_ingest_ts", "event_ts", "delivered_ts", "payment_ts", "status_updated_ts"):
            df = df.withColumn(name, F.to_timestamp(name))
        elif name in ("customer_id", "customer_key", "product_id", "product_key"):
            df = df.withColumn(name, F.col(name).cast("int"))
        elif name in ("sales_key", "anchor_sales_key", "event_key"):
            df = df.withColumn(name, F.col(name).cast("long"))
    return df


def write_raw(table, rows, phase, null_arrival=False):
    """Replace only this fixture's dedicated inputs; refuse foreign ownership."""
    path = f"{ROOT}/Tables/dbo/{table}"
    if notebookutils.fs.exists(path):
        old = spark.read.format("delta").load(path)
        if "dwh_ingest_run_id" not in old.columns or old.filter(
                F.col("dwh_ingest_run_id").isNull() | (F.col("dwh_ingest_run_id") != OWNER)).limit(1).count():
            raise RuntimeError(f"Refusing foreign data at {table}")
    frame(rows, phase, null_arrival).write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(path)


def append_raw(table, rows):
    """Append a deterministic delta, including controlled physical duplicates."""
    frame(rows, "incremental").write.format("delta").mode("append").save(f"{ROOT}/Tables/dbo/{table}")


def execute_transform(name, mode):
    """Execute published business code unchanged, except its terminal exit call.

    Notebook parameters are supplied by this harness. Removing the terminal
    notebook exit allows several deployed transformations in one Spark session;
    it does not change any join, DQ, SCD or merge expression.
    """
    source = TRANSFORM_SOURCES[name]
    body = source.split("# CELL ********************", 1)[1]
    tree = ast.parse(body)
    removed = 0
    for node in list(tree.body):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            if ast.unparse(node.value.func) == "notebookutils.notebook.exit":
                tree.body.remove(node)
                removed += 1
    if removed != 1:
        raise RuntimeError(f"Expected one terminal notebook exit in {name}")
    namespace = {"spark": spark, "notebookutils": notebookutils,
                 "bronze_workspace_id": WORKSPACE_ID, "bronze_lakehouse_id": BRONZE_ID,
                 "pipeline_run_id": OWNER + "_" + mode, "load_mode": mode,
                 "lower_bound_ts": "2025-01-31T23:59:59Z"}
    exec(compile(tree, name, "exec"), namespace)


def snapshot():
    """Collect bounded business values, excluding nondeterministic audit times."""
    sales = spark.table("conformed.fact_sales")
    return {"sales": [row.asDict() for row in sales.select(
                "source_sales_key", "customer_key", "product_key", "sales_amount").orderBy("source_sales_key").collect()],
            "customer_versions": spark.table("conformed.dim_customer").count(),
            "product_versions": spark.table("conformed.dim_product").count(),
            "rejects": spark.table("quality.dq_rejects").count(),
            "order_events": spark.table("conformed.fact_order_event").count()}


# Dimension/reference snapshots contain two serviceable UK postal areas.
customers = [dict(customer_key=1, customer_id=1, customer_business_key="CI-C1",
                  first_name="Fixture", last_name="Customer", marital_status="S", gender="F",
                  create_date="2024-01-01", birth_date="1990-01-01", country="United Kingdom",
                  state_province="England", city="London", postal_code="SW1A 1AA")]
products = [dict(product_key=i, product_id=i, product_business_key=f"CI-P{i}",
                 product_name=f"Fixture Product {i}", product_cost="10.00", product_line="Retail",
                 start_date="2024-01-01", end_date=None, category="Accessories",
                 subcategory="Retail", maintenance_flag="No") for i in (1, 2)]
locations = [dict(location_id=i, country="United Kingdom", region="Europe", subregion="Northern Europe",
                  state_province="England", city=city, postal_code=postal, timezone="Europe/London",
                  market_area="UK", is_active="true", effective_from="2024-01-01", effective_to=None)
             for i, city, postal in ((1, "London", "SW1A 1AA"), (2, "Manchester", "M1 1AE"))]
zones = [dict(postal_code=row["postal_code"], delivery_zone="urban", zone_priority=1,
              standard_sla_days=3, express_sla_days=1, remote_area_flag="false",
              serviceability_flag="true", last_updated_date="2024-01-01") for row in locations]
geo = [dict(country="United Kingdom", country_code="GB", region="Europe", region_code="EU",
            subregion="Northern Europe", market="UK", sales_territory="UK", active_flag="true",
            last_updated_date="2024-01-01")]
coverage = [dict(warehouse_id="CI-W1", warehouse_name="Fixture UK", warehouse_country="United Kingdom",
                 service_region="UK", covered_country="United Kingdom", covered_region="Europe",
                 covered_postal_code=row["postal_code"], delivery_type="standard",
                 serviceability_flag="true", max_sla_days=3, last_updated_date="2024-01-01") for row in locations]


def sale(key, order, date, price, quantity=1, customer=1):
    """One immutable source sales key is one product line on an order."""
    return dict(sales_key=key, order_number=order, product_business_key="CI-P1" if key != 2 else "CI-P2",
                customer_id=customer, order_date=date, ship_date=date, due_date=date,
                sales_amount=str(Decimal(price) * quantity), quantity=quantity, unit_price=price)


def header(order, anchor, date, delivered=False):
    """Order header is the complete population denominator, not sampled events."""
    return dict(order_number=order, anchor_sales_key=anchor, customer_id=1, order_date=date,
                ship_date=date, due_date=date, delivered_ts=date if delivered else None,
                payment_ts=date, status_updated_ts=date, order_status="delivered" if delivered else "created",
                shipment_status="delivered" if delivered else "pending", payment_status="paid")


base_sales = [sale(1, "CI-O1", "2025-01-10", "50.00", 2), sale(2, "CI-O1", "2025-01-10", "50.00")]
for table, rows in {"pg_customer_master": customers, "pg_product_master": products,
                    "s3_location_master": locations, "s3_delivery_zone_lookup": zones,
                    "s3_geo_hierarchy": geo, "s3_warehouse_coverage": coverage,
                    "pg_sales_order_line": base_sales, "pg_order_header": [header("CI-O1", 1, "2025-01-10", True)]}.items():
    # A deliberately pre-existing customer uses inferred prehistory. This is
    # explicit fixture evidence, not a claim of real historical source coverage.
    write_raw(table, rows, "baseline", null_arrival=table == "pg_customer_master")
for table, status in (("pg_order_status_event", "event_status"), ("pg_shipment_status_event", "shipment_status"),
                      ("pg_payment_status_event", "payment_status")):
    write_raw(table, [dict(event_key=1, order_number="CI-O1", event_ts="2025-01-10 00:00:00",
                           **{status: "created" if status == "event_status" else "delivered" if status == "shipment_status" else "paid"})], "baseline")

for name in ("nb_silver_dimensions", "nb_silver_sales", "nb_silver_events", "nb_silver_order_header"):
    execute_transform(name, "baseline")
assert spark.table("conformed.fact_sales").count() == 2, "Baseline line grain failed"
assert spark.table("conformed.fact_sales").agg(F.sum("sales_amount")).first()[0] == Decimal("150.00")
baseline_keys = spark.table("conformed.fact_sales").filter("source_sales_key=1").select("customer_key", "product_key").first()

# Incremental arrivals: SCD changes, one correction, one historical sale, one
# new-period sale, one warning and one known missing-reference hard reject.
append_raw("pg_customer_master", [{**customers[0], "marital_status": "M", "city": "Manchester", "postal_code": "M1 1AE"}])
append_raw("pg_product_master", [{**products[0], "start_date": "2025-02-01", "product_cost": "12.00"}])
correction = sale(1, "CI-O1", "2025-01-10", "55.00", 2)
late = sale(3, "CI-O2", "2025-01-12", "40.00")
new = sale(4, "CI-O3", "2025-03-01", "30.00")
dirty = {**sale(5, "CI-O4", "2025-03-01", "20.00"), "sales_amount": "21.00",
         "ship_date": "2025-02-28", "due_date": "2025-02-28"}
missing = sale(6, "CI-REJECT", "2025-03-01", "10.00", customer=999)
append_raw("pg_sales_order_line", [correction, late, new, new, dirty, missing])
append_raw("pg_order_header", [header("CI-O2", 3, "2025-01-12", True),
                                header("CI-O3", 4, "2025-03-01"), header("CI-O4", 5, "2025-03-01")])
for table, column, status in (("pg_order_status_event", "event_status", "packed"),
                               ("pg_shipment_status_event", "shipment_status", "delayed"),
                               ("pg_payment_status_event", "payment_status", "failed")):
    append_raw(table, [dict(event_key=2, order_number="CI-O2", event_ts="2025-01-12 12:00:00", **{column: status})])

for name in ("nb_silver_dimensions", "nb_silver_sales", "nb_silver_events", "nb_silver_order_header"):
    execute_transform(name, "incremental")
facts = spark.table("conformed.fact_sales")
assert facts.count() == 5 and facts.select("source_sales_key").distinct().count() == 5, "Dedup/merge grain failed"
assert facts.filter("source_sales_key=1").first().sales_amount == Decimal("110.00"), "Correction missed"
assert facts.filter("source_sales_key=3").count() == 1, "Late arrival missed"
old = facts.filter("source_sales_key=3").select("customer_key", "product_key").first()
assert old == baseline_keys, "Historical sale joined current rather than historical dimensions"
current = facts.filter("source_sales_key=4").select("customer_key", "product_key").first()
assert current.customer_key != old.customer_key and current.product_key != old.product_key, "SCD2 change not preserved"
assert spark.table("conformed.dim_customer").filter("dwh_is_current").count() == 1
assert spark.table("conformed.dim_customer").count() == 2, "Customer history lost"
assert spark.table("quality.dq_rejects").count() == 1, "Hard reference reject missing"
assert facts.filter("dq_ship_before_order AND dq_due_before_order AND dq_sales_amount_mismatch").count() == 1
assert spark.table("conformed.fact_order").count() == 4, "Order grain failed"
assert spark.table("conformed.fact_order_event").filter("source_event_key=2 AND dwh_arrival_delay_seconds > 0").count() == 1

before_replay = snapshot()
for name in ("nb_silver_dimensions", "nb_silver_sales", "nb_silver_events", "nb_silver_order_header"):
    execute_transform(name, "incremental")
assert snapshot() == before_replay, "Replay changed business rows or duplicated rejects"
report = {"status": "passed", "scope": "isolated_silver_business_fixture",
          "sales_rows": 5, "order_rows": 4, "reject_rows": 1, "customer_versions": 2,
          "expected_gold_eligible_sales": "230.00", "expected_gold_eligible_lines": 4,
          "source_mutations": 0, "ingestion_checkpoint_updates": 0,
          "checks": ["baseline", "line_grain", "correction", "late_sale", "customer_scd2",
                     "product_scd2", "historical_dimension_join", "soft_dq", "hard_reject",
                     "late_event", "replay", "reject_idempotency"],
          "transform_sha256": {name: hashlib.sha256(source.encode()).hexdigest()
                                for name, source in TRANSFORM_SOURCES.items()}}
notebookutils.fs.mkdirs(f"{ROOT}/Files/cicd_acceptance")
notebookutils.fs.put(f"{ROOT}/Files/cicd_acceptance/silver_report.json", json.dumps(report), True)
notebookutils.notebook.exit(json.dumps(report))
