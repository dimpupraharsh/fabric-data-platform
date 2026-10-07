# Fabric notebook parameters. The build script places this block in a parameter cell.
bronze_workspace_id = "fba1bab2-0098-4b65-9f4f-cb304d71b700"
bronze_lakehouse_id = "ed2e34f8-b837-43c6-b6ba-de68cd7e0079"
pipeline_run_id = "manual"
load_mode = "baseline"
# PARAMETERS_END

"""Create historized dimensions from retained source snapshots.

This notebook is intentionally a rebuild-from-Bronze transformation: the raw
tables remain untouched, while each conformed output is deterministically
reconstructed from the complete retained snapshot history. That makes reruns
safe and lets a late snapshot revise the inferred history in Silver.
"""

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import LongType
import json

spark.conf.set("spark.sql.session.timeZone", "UTC")
spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")

BRONZE_ROOT = (
    f"abfss://{bronze_workspace_id}@onelake.dfs.fabric.microsoft.com/"
    f"{bronze_lakehouse_id}/Tables/dbo"
)
FAR_FUTURE = F.lit("9999-12-31 00:00:00").cast("timestamp")
PREHISTORY = F.lit("1900-01-01 00:00:00").cast("timestamp")


def bronze(table_name: str) -> DataFrame:
    """Read one approved source-shaped Delta table from the Bronze Lakehouse.

    Args:
        table_name: Table name below `Tables/dbo` in the configured Bronze Lakehouse.
    Returns:
        A Spark DataFrame; no rows are changed by this helper.
    """
    return spark.read.format("delta").load(f"{BRONZE_ROOT}/{table_name}")


def norm(column_name: str):
    """Normalize a join-key column for case- and whitespace-insensitive matching."""
    return F.upper(F.trim(F.regexp_replace(F.col(column_name).cast("string"), r"\s+", " ")))


def stable_key(*columns):
    """Create a deterministic numeric key from one or more business-key columns."""
    return F.xxhash64(*[F.coalesce(c.cast("string"), F.lit("<null>")) for c in columns]).cast(LongType())


def record_hash(*columns):
    """Hash tracked attribute values so SCD logic can detect meaningful changes."""
    return F.sha2(
        F.concat_ws("||", *[F.coalesce(c.cast("string"), F.lit("<null>")) for c in columns]),
        256,
    )


def latest_by(df: DataFrame, keys: list[str], *order_columns) -> DataFrame:
    """Return the newest row per key group using descending tie-break columns.

    Args:
        df: Candidate versions, potentially containing retried physical copies.
        keys: Columns that define one entity or entity snapshot.
        order_columns: Timestamp/key columns that make winner selection deterministic.
    Returns:
        One selected source row per key group.
    """
    # A retry can append the same snapshot again; collapse it before creating
    # history so technical duplicates do not look like business changes.
    window = Window.partitionBy(*keys).orderBy(*[c.desc_nulls_last() for c in order_columns])
    return df.withColumn("_rn", F.row_number().over(window)).filter("_rn = 1").drop("_rn")


def write_table(df: DataFrame, table_name: str, partition_columns: list[str] | None = None) -> None:
    """Rebuild a deterministic Silver dimension/bridge as a Delta table.

    Args:
        df: Complete output for this dimension or bridge.
        table_name: Fully qualified Silver table name.
        partition_columns: Optional low-cardinality/date partition columns.
    Returns:
        None. Replaces this Silver output only; Bronze is never modified.
    """
    writer = df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    if partition_columns:
        writer = writer.partitionBy(*partition_columns)
    writer.saveAsTable(table_name)


for schema_name in ("conformed", "reference", "quality", "ops"):
    # Create Silver namespaces on first deployment without changing Bronze.
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")

# Location SCD2: each retained arrival is a point-in-time view of geography.
# Source effective dates win when provided; otherwise the snapshot arrival
# defines when Silver first knew about the change.
locations = bronze("s3_location_master")
delivery = bronze("s3_delivery_zone_lookup")
geo = bronze("s3_geo_hierarchy")

locations = (
    locations
    .withColumn("country_norm", norm("country"))
    .withColumn("postal_code_norm", norm("postal_code"))
    .withColumn("region_norm", norm("region"))
    .withColumn("subregion_norm", norm("subregion"))
    .withColumn("source_effective_from", F.to_timestamp("effective_from"))
    .withColumn("source_effective_to", F.to_timestamp("effective_to"))
    .withColumn("_snapshot_ts", F.coalesce(F.col("dwh_ingest_ts"), F.to_timestamp("effective_from"), PREHISTORY))
)
locations = latest_by(
    locations,
    ["location_id", "_snapshot_ts"],
    F.col("dwh_ingest_ts"),
    F.col("source_effective_from"),
)

delivery = (
    delivery
    .withColumn("postal_code_norm", norm("postal_code"))
    .withColumn("_snapshot_ts", F.coalesce(F.col("dwh_ingest_ts"), F.to_timestamp("last_updated_date"), PREHISTORY))
)
delivery = latest_by(
    delivery,
    ["postal_code_norm", "_snapshot_ts"],
    F.col("dwh_ingest_ts"),
    F.to_timestamp("last_updated_date"),
)

geo = (
    geo
    .withColumn("country_norm", norm("country"))
    .withColumn("region_norm", norm("region"))
    .withColumn("subregion_norm", norm("subregion"))
    .withColumn("_snapshot_ts", F.coalesce(F.col("dwh_ingest_ts"), F.to_timestamp("last_updated_date"), PREHISTORY))
)
geo = latest_by(
    geo,
    ["country_norm", "region_norm", "subregion_norm", "_snapshot_ts"],
    F.col("dwh_ingest_ts"),
    F.to_timestamp("last_updated_date"),
)

# Join source snapshots only within the same snapshot version. This avoids
# pairing geography from one reference refresh with a zone from another.
location_current = (
    locations.alias("l")
    .join(
        delivery.alias("d"),
        (F.col("l.postal_code_norm") == F.col("d.postal_code_norm"))
        & (F.col("l._snapshot_ts") == F.col("d._snapshot_ts")),
        "left",
    )
    .join(
        geo.alias("g"),
        (F.col("l.country_norm") == F.col("g.country_norm"))
        & (F.col("l.region_norm") == F.col("g.region_norm"))
        & (F.col("l.subregion_norm") == F.col("g.subregion_norm"))
        & (F.col("l._snapshot_ts") == F.col("g._snapshot_ts")),
        "left",
    )
    .select(
        F.col("l.location_id").cast("long").alias("source_location_id"),
        F.col("l.country"), F.col("g.country_code"), F.col("l.region"), F.col("g.region_code"),
        F.col("l.subregion"), F.col("l.state_province"), F.col("l.city"), F.col("l.postal_code"),
        F.col("l.timezone"), F.col("l.market_area"), F.col("g.market"), F.col("g.sales_territory"),
        F.col("d.delivery_zone"), F.col("d.zone_priority").cast("int"),
        F.col("d.standard_sla_days").cast("int"), F.col("d.express_sla_days").cast("int"),
        F.col("d.remote_area_flag").cast("boolean"), F.col("d.serviceability_flag").cast("boolean"),
        F.col("l.is_active").cast("boolean").alias("is_active"),
        F.col("l.country_norm").alias("country_normalized"),
        F.col("l.postal_code_norm").alias("postal_code_normalized"),
        F.col("l.source_effective_from"), F.col("l.source_effective_to"),
        F.col("l._snapshot_ts").alias("snapshot_ts"),
        F.col("l.dwh_ingest_run_id"), F.col("l.dwh_ingest_batch_id"), F.col("l.dwh_ingest_ts"),
    )
)

# Hash only tracked attributes for change detection; snapshot/load metadata is
# intentionally excluded so an unchanged file does not manufacture SCD2 rows.
location_entity = stable_key(F.col("country_normalized"), F.col("postal_code_normalized"))
location_type2_hash = record_hash(
    F.col("country"), F.col("country_code"), F.col("region"), F.col("region_code"),
    F.col("subregion"), F.col("state_province"), F.col("city"), F.col("postal_code"),
    F.col("timezone"), F.col("market_area"), F.col("market"), F.col("sales_territory"),
    F.col("delivery_zone"), F.col("zone_priority"), F.col("standard_sla_days"),
    F.col("express_sla_days"), F.col("remote_area_flag"), F.col("serviceability_flag"), F.col("is_active"),
)

# Keep the first version and only later rows whose Type 2 attributes changed.
location_changes = (
    location_current
    .withColumn("location_entity_key", location_entity)
    .withColumn("dwh_type2_hash", location_type2_hash)
    .withColumn("candidate_from", F.coalesce(F.col("source_effective_from"), F.col("snapshot_ts"), PREHISTORY))
)
location_change_window = Window.partitionBy("location_entity_key").orderBy("candidate_from", "snapshot_ts")
location_changes = (
    location_changes
    .withColumn("_previous_hash", F.lag("dwh_type2_hash").over(location_change_window))
    .filter(F.col("_previous_hash").isNull() | (F.col("_previous_hash") != F.col("dwh_type2_hash")))
    .drop("_previous_hash")
)

first_location_window = Window.partitionBy("location_entity_key").orderBy(F.col("candidate_from").asc(), F.col("snapshot_ts").asc())
first_locations = location_changes.withColumn("_rn", F.row_number().over(first_location_window)).filter("_rn = 1").drop("_rn")
prehistory_locations = (
    first_locations
    .filter(F.col("candidate_from") > PREHISTORY)
    .withColumn("dwh_effective_from", PREHISTORY)
    .withColumn("dwh_effective_to", F.col("candidate_from"))
    .withColumn("dwh_is_current", F.lit(False))
    .withColumn("dwh_is_inferred", F.lit(True))
    .withColumn("dwh_history_assumed", F.lit(True))
)

location_version_window = Window.partitionBy("location_entity_key").orderBy("candidate_from", "snapshot_ts")
dated_locations = (
    location_changes
    .withColumn("dwh_effective_from", F.col("candidate_from"))
    .withColumn("dwh_effective_to", F.coalesce(F.lead("candidate_from").over(location_version_window), FAR_FUTURE))
    .withColumn("dwh_is_current", F.col("dwh_effective_to") == FAR_FUTURE)
    .withColumn("dwh_is_inferred", F.lit(False))
    .withColumn("dwh_history_assumed", F.lit(False))
)

dim_location = prehistory_locations.unionByName(dated_locations, allowMissingColumns=True)
dim_location = (
    dim_location
    .withColumn("location_key", stable_key(F.col("location_entity_key"), F.col("dwh_effective_from")))
    .withColumn("dwh_record_hash", record_hash(F.col("location_entity_key"), F.col("dwh_effective_from"), F.col("dwh_type2_hash")))
    .withColumn("dwh_source_system", F.lit("aws_s3"))
    .withColumn("dwh_load_ts", F.current_timestamp())
    .withColumn("dwh_pipeline_run_id", F.lit(pipeline_run_id))
    .drop("candidate_from", "snapshot_ts")
)

# An explicit unknown member protects downstream joins without masking missing-reference DQ.
unknown_location = dim_location.limit(1)
unknown_location_values = {
    "source_location_id": -1, "country": "Unknown", "country_code": "UNK", "region": "Unknown",
    "region_code": "UNK", "subregion": "Unknown", "state_province": "Unknown", "city": "Unknown",
    "postal_code": "UNKNOWN", "timezone": "UTC", "market_area": "Unknown", "market": "Unknown",
    "sales_territory": "Unknown", "delivery_zone": "Unknown", "zone_priority": 0,
    "standard_sla_days": 0, "express_sla_days": 0, "remote_area_flag": False,
    "serviceability_flag": False, "is_active": False, "country_normalized": "UNKNOWN",
    "postal_code_normalized": "UNKNOWN", "source_effective_from": "1900-01-01",
    "source_effective_to": "9999-12-31", "dwh_ingest_run_id": "system",
    "dwh_ingest_batch_id": "system", "dwh_ingest_ts": "1900-01-01",
    "location_entity_key": 0, "dwh_type2_hash": "unknown", "dwh_effective_from": "1900-01-01",
    "dwh_effective_to": "9999-12-31", "dwh_is_current": True, "dwh_is_inferred": True,
    "dwh_history_assumed": True, "location_key": 0, "dwh_record_hash": "unknown",
    "dwh_source_system": "system", "dwh_load_ts": "1900-01-01", "dwh_pipeline_run_id": pipeline_run_id,
}
for field in dim_location.schema.fields:
    unknown_location = unknown_location.withColumn(
        field.name,
        F.lit(unknown_location_values[field.name]).cast(field.dataType),
    )
dim_location = dim_location.unionByName(unknown_location)
write_table(dim_location, "conformed.dim_location")

# Category SCD1: category labels are corrected in place because historical
# category wording is not a business-history requirement in this project.
products_raw = bronze("pg_product_master")
products_raw = products_raw.withColumn(
    "_version_ts",
    F.coalesce(F.col("dwh_ingest_ts"), F.col("dwh_load_ts"), F.to_timestamp("start_date"), PREHISTORY),
)
products_latest = latest_by(
    products_raw,
    ["product_business_key"],
    F.col("_version_ts"), F.col("dwh_load_ts"), F.col("product_key"),
)
category_source = (
    products_latest
    .select(
        F.coalesce(F.trim("category"), F.lit("Unknown")).alias("category"),
        F.coalesce(F.trim("subcategory"), F.lit("Unknown")).alias("subcategory"),
    )
    .distinct()
    .filter(~((F.lower(F.col("category")) == "unknown") & (F.lower(F.col("subcategory")) == "unknown")))
)
dim_category = (
    category_source
    .withColumn("category_key", stable_key(F.upper("category"), F.upper("subcategory")))
    .withColumn("dwh_record_hash", record_hash(F.col("category"), F.col("subcategory")))
    .withColumn("dwh_source_system", F.lit("postgresql"))
    .withColumn("dwh_load_ts", F.current_timestamp())
    .withColumn("dwh_pipeline_run_id", F.lit(pipeline_run_id))
)
unknown_category = dim_category.limit(1)
unknown_category_values = {
    "category": "Unknown", "subcategory": "Unknown", "category_key": 0,
    "dwh_record_hash": "unknown", "dwh_source_system": "system",
    "dwh_load_ts": "1900-01-01", "dwh_pipeline_run_id": pipeline_run_id,
}
for field in dim_category.schema.fields:
    unknown_category = unknown_category.withColumn(
        field.name,
        F.lit(unknown_category_values[field.name]).cast(field.dataType),
    )
dim_category = dim_category.unionByName(unknown_category).dropDuplicates(["category", "subcategory"])
write_table(dim_category, "conformed.dim_category")

# Product SCD2: retain attribute changes as versions and use product start/end
# dates as source evidence, falling back to snapshot arrival when absent.
latest_names = products_latest.select(
    "product_business_key", F.col("product_name").alias("latest_product_name")
)
# Product cost and classification are effective-dated; the product name is
# corrected to the latest spelling without creating a new history version.
product_versions = (
    products_raw
    .withColumn("candidate_from", F.coalesce(F.to_timestamp("start_date"), F.col("_version_ts"), PREHISTORY))
    .withColumn("source_end_date", F.to_date("end_date"))
)
product_versions = latest_by(
    product_versions,
    ["product_business_key", "candidate_from"],
    F.col("_version_ts"), F.col("dwh_load_ts"), F.col("product_key"),
)
product_versions = product_versions.drop("product_name").join(latest_names, "product_business_key", "left")
product_versions = (
    product_versions
    .withColumn("product_name", F.col("latest_product_name"))
    .withColumn("category", F.coalesce(F.trim("category"), F.lit("Unknown")))
    .withColumn("subcategory", F.coalesce(F.trim("subcategory"), F.lit("Unknown")))
    .withColumn("product_entity_key", stable_key(F.lit("product"), F.col("product_business_key")))
    .withColumn("dwh_type2_hash", record_hash(
        F.col("product_cost"), F.col("product_line"), F.col("category"),
        F.col("subcategory"), F.col("maintenance_flag"),
    ))
)
product_window = Window.partitionBy("product_business_key").orderBy("candidate_from", "_version_ts")
product_versions = (
    product_versions
    .withColumn("_previous_hash", F.lag("dwh_type2_hash").over(product_window))
    .filter(F.col("_previous_hash").isNull() | (F.col("_previous_hash") != F.col("dwh_type2_hash")))
    .drop("_previous_hash")
)
first_product_window = Window.partitionBy("product_business_key").orderBy(F.col("candidate_from").asc(), F.col("_version_ts").asc())
first_products = product_versions.withColumn("_rn", F.row_number().over(first_product_window)).filter("_rn = 1").drop("_rn")
prehistory_products = (
    first_products
    .filter(F.col("candidate_from") > PREHISTORY)
    .withColumn("dwh_effective_from", PREHISTORY)
    .withColumn("dwh_effective_to", F.col("candidate_from"))
    .withColumn("dwh_is_current", F.lit(False))
    .withColumn("dwh_is_inferred", F.lit(True))
    .withColumn("dwh_history_assumed", F.lit(True))
)
product_interval_window = Window.partitionBy("product_business_key").orderBy("candidate_from", "_version_ts")
dated_products = (
    product_versions
    .withColumn("dwh_effective_from", F.col("candidate_from"))
    .withColumn("dwh_effective_to", F.coalesce(F.lead("candidate_from").over(product_interval_window), FAR_FUTURE))
    .withColumn("dwh_is_current", F.col("dwh_effective_to") == FAR_FUTURE)
    .withColumn("dwh_is_inferred", F.lit(False))
    .withColumn("dwh_history_assumed", F.lit(False))
)
dim_product_versions = prehistory_products.unionByName(dated_products, allowMissingColumns=True).alias("p")
category_lookup = dim_category.select("category_key", "category", "subcategory").alias("c")
dim_product = (
    dim_product_versions
    .join(
        category_lookup,
        (F.col("p.category") == F.col("c.category"))
        & (F.col("p.subcategory") == F.col("c.subcategory")),
        "left",
    )
    .select("p.*", F.col("c.category_key"))
    .withColumn("category_key", F.coalesce(F.col("category_key"), F.lit(0).cast("long")))
    .withColumn("product_key", stable_key(F.col("product_entity_key"), F.col("dwh_effective_from")))
    .withColumn("dwh_source_interval_repaired", F.col("source_end_date").isNotNull() & (F.col("source_end_date") < F.to_date("candidate_from")))
    .withColumn("dwh_record_hash", record_hash(F.col("product_entity_key"), F.col("dwh_effective_from"), F.col("dwh_type2_hash")))
    .withColumn("dwh_source_system", F.lit("postgresql"))
    .withColumn("dwh_load_ts", F.current_timestamp())
    .withColumn("dwh_pipeline_run_id", F.lit(pipeline_run_id))
    .drop("candidate_from", "_version_ts", "latest_product_name")
    .dropDuplicates(["product_key"])
)
write_table(dim_product, "conformed.dim_product")

# Customer mixed SCD: descriptive identity attributes are Type 2; selected
# corrections are Type 1 so non-historical cleanup does not create versions.
customers_raw = bronze("pg_customer_master")
customers_raw = (
    customers_raw
    .withColumn("country_normalized", norm("country"))
    .withColumn("postal_code_normalized", norm("postal_code"))
    .withColumn("_snapshot_ts", F.coalesce(F.col("dwh_ingest_ts"), F.col("dwh_load_ts"), PREHISTORY))
)
# Name, birth date, and gender corrections use the latest known values (SCD1).
# Marital status and geographic assignment remain snapshot-specific (SCD2).
latest_customer_corrections = latest_by(
    customers_raw,
    ["customer_id"],
    F.col("_snapshot_ts"), F.col("dwh_load_ts"), F.col("customer_key"),
).select(
    "customer_id",
    F.col("first_name").alias("latest_first_name"),
    F.col("last_name").alias("latest_last_name"),
    F.col("birth_date").alias("latest_birth_date"),
    F.col("gender").alias("latest_gender"),
)
customer_snapshots = latest_by(
    customers_raw,
    ["customer_id", "_snapshot_ts"],
    F.col("dwh_load_ts"), F.col("customer_key"),
).join(latest_customer_corrections, "customer_id", "left")
customer_snapshots = (
    customer_snapshots
    .withColumn("first_name", F.col("latest_first_name"))
    .withColumn("last_name", F.col("latest_last_name"))
    .withColumn("birth_date", F.col("latest_birth_date"))
    .withColumn("gender", F.col("latest_gender"))
    .withColumn("candidate_from", F.when(F.col("dwh_ingest_ts").isNull(), PREHISTORY).otherwise(F.col("_snapshot_ts")))
    .withColumn("customer_entity_key", stable_key(F.lit("customer"), F.col("customer_id")))
    .withColumn("location_entity_key", stable_key(F.col("country_normalized"), F.col("postal_code_normalized")))
    .withColumn("dwh_type2_hash", record_hash(
        F.col("marital_status"), F.col("country_normalized"), F.col("state_province"),
        F.col("city"), F.col("postal_code_normalized"),
    ))
)
customer_change_window = Window.partitionBy("customer_id").orderBy("candidate_from", "_snapshot_ts")
customer_changes = (
    customer_snapshots
    .withColumn("_previous_hash", F.lag("dwh_type2_hash").over(customer_change_window))
    .filter(F.col("_previous_hash").isNull() | (F.col("_previous_hash") != F.col("dwh_type2_hash")))
    .drop("_previous_hash")
)
customer_interval_window = Window.partitionBy("customer_id").orderBy("candidate_from", "_snapshot_ts")
dim_customer = (
    customer_changes
    .withColumn("dwh_effective_from", F.col("candidate_from"))
    .withColumn("dwh_effective_to", F.coalesce(F.lead("candidate_from").over(customer_interval_window), FAR_FUTURE))
    .withColumn("dwh_is_current", F.col("dwh_effective_to") == FAR_FUTURE)
    .withColumn("dwh_is_inferred", F.lit(False))
    .withColumn("dwh_history_assumed", F.col("candidate_from") == PREHISTORY)
    .withColumn("customer_key", stable_key(F.col("customer_entity_key"), F.col("dwh_effective_from")))
    .withColumn("dwh_record_hash", record_hash(F.col("customer_entity_key"), F.col("dwh_effective_from"), F.col("dwh_type2_hash")))
    .withColumn("dwh_source_system", F.lit("postgresql"))
    .withColumn("dwh_load_ts", F.current_timestamp())
    .withColumn("dwh_pipeline_run_id", F.lit(pipeline_run_id))
    .drop("candidate_from", "_snapshot_ts", "latest_first_name", "latest_last_name", "latest_birth_date", "latest_gender")
)
write_table(dim_customer, "conformed.dim_customer")

# Warehouse coverage is effective-dated reference history, not a transaction
# fact. Stable warehouse/postal/service keys identify the coverage relationship.
# Preserve one-to-many warehouse coverage as an effective-dated bridge. Never
# join this bridge directly to sales without a deliberate warehouse rule.
coverage = bronze("s3_warehouse_coverage")
coverage = (
    coverage
    .withColumn("covered_country_normalized", norm("covered_country"))
    .withColumn("covered_postal_code_normalized", norm("covered_postal_code"))
    .withColumn("dwh_effective_from", F.coalesce(F.to_timestamp("last_updated_date"), F.col("dwh_ingest_ts"), PREHISTORY))
    .withColumn("coverage_entity_key", stable_key(
        F.col("warehouse_id"), F.col("covered_country_normalized"),
        F.col("covered_postal_code_normalized"), F.col("delivery_type"),
    ))
)
coverage = latest_by(
    coverage,
    ["coverage_entity_key", "dwh_effective_from"],
    F.col("dwh_ingest_ts"), F.to_timestamp("last_updated_date"),
)
coverage_window = Window.partitionBy("coverage_entity_key").orderBy("dwh_effective_from")
bridge_coverage = (
    coverage
    .withColumn("dwh_effective_to", F.coalesce(F.lead("dwh_effective_from").over(coverage_window), FAR_FUTURE))
    .withColumn("dwh_is_current", F.col("dwh_effective_to") == FAR_FUTURE)
    .withColumn("warehouse_coverage_key", stable_key(F.col("coverage_entity_key"), F.col("dwh_effective_from")))
    .withColumn("location_entity_key", stable_key(F.col("covered_country_normalized"), F.col("covered_postal_code_normalized")))
    .withColumn("serviceability_flag", F.col("serviceability_flag").cast("boolean"))
    .withColumn("max_sla_days", F.col("max_sla_days").cast("int"))
    .withColumn("dwh_record_hash", record_hash(
        F.col("coverage_entity_key"), F.col("serviceability_flag"), F.col("max_sla_days"), F.col("dwh_effective_from"),
    ))
    .withColumn("dwh_source_system", F.lit("aws_s3"))
    .withColumn("dwh_load_ts", F.current_timestamp())
    .withColumn("dwh_pipeline_run_id", F.lit(pipeline_run_id))
)
write_table(bridge_coverage, "reference.bridge_warehouse_coverage")

result = {
    "status": "succeeded",
    "pipeline_run_id": pipeline_run_id,
    "load_mode": load_mode,
    "dim_location_rows": dim_location.count(),
    "dim_customer_rows": dim_customer.count(),
    "dim_category_rows": dim_category.count(),
    "dim_product_rows": dim_product.count(),
    "warehouse_coverage_rows": bridge_coverage.count(),
}
notebookutils.notebook.exit(json.dumps(result))
