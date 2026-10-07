# Fabric notebook parameters. The build script places this block in a parameter cell.
pipeline_run_id = "manual"
max_age_minutes = 180
# PARAMETERS_END

"""Check published Gold against the consumer semantic model after each run.

Inputs are the single-row Gold KPI audit and one DAX result. The notebook
appends its result to the control Warehouse and raises on failure, making the
scheduled parent fail visibly without changing Gold or its watermarks.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import time
import uuid


WORKSPACE_ID = "fba1bab2-0098-4b65-9f4f-cb304d71b700"
MODEL_ID = "fb836d66-97d2-4ba6-a084-c0ddef57159a"
GOLD_TABLE = "wh_retail_gold.gold.kpi_audit"
HEALTH_TABLE = "wh_retail_control.control.ctl_gold_serving_health_run"
MODEL_QUERY = (
    'EVALUATE ROW("AuditTime", MAX(\'kpi_audit\'[audited_at_utc]), '
    '"Sales", [Gross Booked Sales], "Lines", [Sales Lines], '
    '"Orders", [Eligible Orders], "SLA", [SLA Eligible Deliveries])'
)
METRIC_COLUMNS = {
    "Sales": "eligible_gross_booked_sales_amount",
    "Lines": "eligible_sales_line_count",
    "Orders": "eligible_order_count",
    "SLA": "shipping_sla_eligible_order_count",
}


def as_utc(value: datetime | str) -> datetime:
    """Interpret unzoned Warehouse/DAX audit timestamps as UTC."""
    result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def compare(gold: dict, model: dict, checked_at: datetime, age_limit_minutes: int) -> list[str]:
    """Return stable failure codes for freshness and four certified metrics."""
    issues = []
    gold_time = as_utc(gold["AuditTime"])
    model_time = as_utc(model["AuditTime"])
    age = checked_at - gold_time
    if age < timedelta(minutes=-5) or age > timedelta(minutes=age_limit_minutes):
        issues.append("gold_publication_stale")
    if abs((gold_time - model_time).total_seconds()) > 1:
        issues.append("semantic_audit_version_mismatch")
    for name in METRIC_COLUMNS:
        tolerance = Decimal("0.01") if name == "Sales" else Decimal(0)
        if abs(Decimal(str(gold[name])) - Decimal(str(model[name]))) > tolerance:
            issues.append(f"{name.lower()}_mismatch")
    return issues


def warehouse_audit() -> dict:
    """Read only the latest serving audit, not the large sales fact."""
    import com.microsoft.spark.fabric

    rows = spark.read.synapsesql(GOLD_TABLE).limit(2).collect()
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one Gold KPI audit row; observed {len(rows)}")
    row = rows[0].asDict()
    return {"AuditTime": row["audited_at_utc"], **{
        name: row[column] for name, column in METRIC_COLUMNS.items()
    }}


def semantic_audit() -> dict:
    """Query the live semantic model under the pipeline notebook identity."""
    import notebookutils
    import requests

    token = notebookutils.credentials.getToken("pbi")
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/"
        f"datasets/{MODEL_ID}/executeQueries"
    )
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"queries": [{"query": MODEL_QUERY}]},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Semantic query rejected: {payload['error']}")
    row = payload["results"][0]["tables"][0]["rows"][0]
    return {name: row[f"[{name}]"] for name in ("AuditTime", *METRIC_COLUMNS)}


def record_result(result: dict) -> None:
    """Append an immutable operator record to the control Warehouse."""
    import com.microsoft.spark.fabric
    from pyspark.sql.types import StringType, StructField, StructType, TimestampType

    schema = StructType([
        StructField("health_run_id", StringType(), False),
        StructField("pipeline_run_id", StringType(), False),
        StructField("checked_at_utc", TimestampType(), False),
        StructField("gold_audited_at_utc", TimestampType(), True),
        StructField("model_audited_at_utc", TimestampType(), True),
        StructField("check_status", StringType(), False),
        StructField("failure_reason", StringType(), True),
        StructField("comparison_json", StringType(), False),
    ])
    values = (
        result["health_run_id"], result["pipeline_run_id"],
        result["checked_at_utc"].replace(tzinfo=None),
        result["gold_audited_at_utc"].replace(tzinfo=None) if result["gold_audited_at_utc"] else None,
        result["model_audited_at_utc"].replace(tzinfo=None) if result["model_audited_at_utc"] else None,
        result["check_status"], result["failure_reason"], result["comparison_json"],
    )
    spark.createDataFrame([values], schema).write.mode("append").synapsesql(HEALTH_TABLE)


def run_check() -> dict:
    """Retry short Direct Lake framing lag, persist the verdict, then fail closed."""
    gold = None
    model = None
    issues = []
    checked_at = datetime.now(timezone.utc)
    try:
        gold = warehouse_audit()
        for attempt in range(6):
            try:
                model = semantic_audit()
                issues = compare(gold, model, datetime.now(timezone.utc), int(max_age_minutes))
            except Exception as error:
                issues = [f"semantic_query_error: {str(error)[:300]}"]
            if not issues:
                break
            # Waiting can fix Direct Lake framing lag, but cannot make an
            # already-old Gold publication newly current.
            if "gold_publication_stale" in issues:
                break
            if attempt < 5:
                time.sleep(30)
    except Exception as error:
        issues = [f"gold_audit_error: {str(error)[:300]}"]

    result = {
        "health_run_id": str(uuid.uuid4()),
        "pipeline_run_id": str(pipeline_run_id),
        "checked_at_utc": checked_at,
        "gold_audited_at_utc": as_utc(gold["AuditTime"]) if gold else None,
        "model_audited_at_utc": as_utc(model["AuditTime"]) if model else None,
        "check_status": "failed" if issues else "passed",
        "failure_reason": ", ".join(issues) if issues else None,
        "comparison_json": json.dumps({
            "gold": {k: str(v) for k, v in gold.items()} if gold else None,
            "semantic": {k: str(v) for k, v in model.items()} if model else None,
        })[:4000],
    }
    record_result(result)
    if issues:
        raise RuntimeError(f"Gold serving health failed: {result['failure_reason']}")
    print(json.dumps({"status": "passed", "health_run_id": result["health_run_id"]}))
    return result


if __name__ == "__main__":
    run_check()
