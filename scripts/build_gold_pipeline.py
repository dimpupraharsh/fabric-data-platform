#!/usr/bin/env python3
"""Compile versioned Gold SQL into a deployable Fabric Data Pipeline definition.

The generated pipeline executes inside Fabric. This local script is only the
source-controlled deployment tool; daily publication needs no local runtime.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "fabric/gold_warehouse"
DEST = ROOT / "fabric/pipelines/gold/pl_gold_orchestrator.pipeline-content.json"
GOLD_CONNECTION_ID = "0a85b5ac-b0d0-4686-9de2-c3bf62dac800"
TABLES = (
    "dim_category", "dim_customer", "dim_product", "dim_location",
    "fact_sales", "mart_daily_sales", "mart_monthly_sales",
    "mart_customer_spend", "mart_product_performance",
    "mart_category_performance", "mart_geography_sales", "mart_sales_yoy",
    "fact_order", "mart_order_lifecycle", "mart_shipping_sla",
    "mart_payment_status", "mart_customer_order_frequency", "dim_date",
    "dim_customer_current", "kpi_audit",
)


def sql_blocks(path: Path, *, build_schema: bool = False) -> list[dict[str, str]]:
    """Split GO batches; optionally redirect every Gold reference to the candidate schema."""
    contents = path.read_text()
    if build_schema:
        contents = contents.replace("gold.", "gold_build.")
        contents = contents.replace("name = 'gold'", "name = 'gold_build'")
        contents = contents.replace("CREATE SCHEMA gold", "CREATE SCHEMA gold_build")
    blocks = [part.strip() for part in re.split(r"^\s*GO\s*$", contents, flags=re.M | re.I) if part.strip()]
    return [{"type": "Query", "text": block} for block in blocks]


def publication_sql() -> str:
    """Replace live rows atomically while retaining semantic-model table identities."""
    checks = "\n".join(
        f"IF OBJECT_ID('gold_build.{name}', 'U') IS NULL "
        f"RAISERROR('Missing audited Gold candidate: {name}', 16, 1);"
        for name in TABLES
    )
    column_signature = "name, column_id, system_type_id, max_length, precision, scale, is_nullable"
    contracts = "\n".join(
        "IF EXISTS ("
        f"SELECT {column_signature} FROM sys.columns WHERE object_id = OBJECT_ID('gold.{name}') "
        f"EXCEPT SELECT {column_signature} FROM sys.columns WHERE object_id = OBJECT_ID('gold_build.{name}')"
        ") OR EXISTS ("
        f"SELECT {column_signature} FROM sys.columns WHERE object_id = OBJECT_ID('gold_build.{name}') "
        f"EXCEPT SELECT {column_signature} FROM sys.columns WHERE object_id = OBJECT_ID('gold.{name}')"
        ") "
        f"RAISERROR('Gold schema contract changed: {name}', 16, 1);"
        for name in TABLES
    )
    copies = "\n".join(
        f"TRUNCATE TABLE gold.{name};\n"
        f"INSERT INTO gold.{name} SELECT * FROM gold_build.{name};"
        for name in TABLES
    )
    return (
        f"{checks}\n{contracts}\n"
        "BEGIN TRY\n"
        "    BEGIN TRANSACTION;\n"
        f"{copies}\n"
        "    COMMIT TRANSACTION;\n"
        "END TRY\n"
        "BEGIN CATCH\n"
        "    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;\n"
        "    THROW;\n"
        "END CATCH;"
    )


def activity(name: str, predecessor: str | None, sql_text: list[dict[str, str]], description: str) -> dict:
    """Create a serial, monitored Warehouse Script activity with a plain description."""
    return {
        "name": name,
        "type": "Script",
        "dependsOn": [] if predecessor is None else [{"activity": predecessor, "dependencyConditions": ["Succeeded"]}],
        "policy": {"timeout": "0.04:00:00", "retry": 0, "retryIntervalInSeconds": 30,
                   "secureOutput": False, "secureInput": False},
        "typeProperties": {"scripts": sql_text, "scriptBlockExecutionTimeout": "04:00:00"},
        "externalReferences": {"connection": GOLD_CONNECTION_ID},
        "description": description,
    }


def main() -> None:
    # Candidate tables can be rebuilt freely; the live schema is never dropped.
    drop_sql = "\n".join(f"DROP TABLE IF EXISTS gold_build.{name};" for name in reversed(TABLES))
    drop_sql = (
        "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'gold_build') "
        "EXEC('CREATE SCHEMA gold_build');\n" + drop_sql
    )
    stages = [
        activity(
            "ValidateSilverReady", None,
            [{"type": "Query", "text": (
                "IF NOT EXISTS (SELECT TOP 1 1 FROM [lh_retail_silver].[conformed].[fact_sales]) "
                "RAISERROR('Silver sales fact is empty.',16,1); "
                "IF NOT EXISTS (SELECT TOP 1 1 FROM [lh_retail_silver].[conformed].[fact_order]) "
                "RAISERROR('Silver order header fact is empty.',16,1);"
            )}],
            "Requires nonempty Silver sales-line and complete-population order facts before preparing a Gold candidate.",
        ),
        activity(
            "ClearPriorGoldBuild", "ValidateSilverReady",
            [{"type": "Query", "text": drop_sql}],
            "Removes only the previous candidate tables; currently served Gold and the semantic model stay available.",
        ),
        activity(
            "BuildGoldDimensions", "ClearPriorGoldBuild",
            sql_blocks(SQL / "10_create_gold_schema.sql", build_schema=True),
            "Builds candidate SCD2 customer, product, location, and category dimensions from conformed Silver.",
        ),
        activity(
            "BuildGoldSalesFact", "BuildGoldDimensions",
            sql_blocks(SQL / "11_create_sales_fact.sql", build_schema=True),
            "Builds one candidate row per Silver sales line with order-identity and eligibility audit flags.",
        ),
        activity(
            "BuildGoldSalesMarts", "BuildGoldSalesFact",
            sql_blocks(SQL / "12_create_sales_marts.sql", build_schema=True),
            "Builds candidate daily, monthly, customer, product, category, geography, and complete-year YoY summaries.",
        ),
        activity(
            "BuildGoldOrderMarts", "BuildGoldSalesMarts",
            sql_blocks(SQL / "15_create_order_marts.sql", build_schema=True),
            "Builds candidate order state, lifecycle, payment, shipping SLA, and repeat-order marts from full-population headers.",
        ),
        activity(
            "BuildSemanticDimensions", "BuildGoldOrderMarts",
            sql_blocks(SQL / "17_create_semantic_dimensions.sql", build_schema=True),
            "Builds candidate continuous date and current-customer dimensions for stable semantic relationships.",
        ),
        activity(
            "AuditGoldCandidate", "BuildSemanticDimensions",
            sql_blocks(SQL / "16_kpi_audit.sql", build_schema=True),
            "Audits candidate denominators and blocks publication if grain, coverage, revenue, or mart totals disagree.",
        ),
        activity(
            "PublishGoldAtomically", "AuditGoldCandidate",
            [{"type": "Query", "text": publication_sql()}],
            "Copies audited candidate rows into existing Gold tables in one rollback-capable transaction; table identities remain stable.",
        ),
        activity(
            "VerifyPublishedGold", "PublishGoldAtomically",
            [{"type": "Query", "text": (
                "IF (SELECT COUNT(*) FROM gold.kpi_audit) <> 1 "
                "RAISERROR('Published Gold audit must contain exactly one row.', 16, 1); "
                "IF EXISTS (SELECT * FROM gold.kpi_audit EXCEPT SELECT * FROM gold_build.kpi_audit) "
                "OR EXISTS (SELECT * FROM gold_build.kpi_audit EXCEPT SELECT * FROM gold.kpi_audit) "
                "RAISERROR('Published Gold audit differs from audited candidate.', 16, 1);"
            )}],
            "Confirms the committed serving audit row exactly matches the candidate that passed the KPI gate.",
        ),
    ]
    payload = {"properties": {
        "concurrency": 1,
        "description": (
            "Builds and audits Gold candidates, then transactionally replaces live rows without dropping "
            "semantic-model tables. Gross booked sales is not net revenue."
        ),
        "activities": stages,
    }}
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(payload, indent=2) + "\n")
    print(DEST)


if __name__ == "__main__":
    main()
