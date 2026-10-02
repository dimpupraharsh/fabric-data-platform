"""Run isolated Silver/Gold business acceptance in Fabric Test only.

Creates explicitly owned acceptance assets in the existing Test workspace. Uses
published Silver code and Gold SQL, not copies of Production business data.
No real source writes, ingestion checkpoint changes, schedules or deletion.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse

import requests

from export_sql_schema import connect
from fabric_api import BASE, FabricAPI
from migrate import migrate

ROOT = Path(__file__).resolve().parents[1]
OWNER = "retail_ci_business_fixture_v1"
TEST_WORKSPACE = "74fa18f7-20d4-4800-9051-6796923b397a"
PRODUCTION = "fba1bab2-0098-4b65-9f4f-cb304d71b700"
TRANSFORMS = ("nb_silver_dimensions", "nb_silver_sales", "nb_silver_events", "nb_silver_order_header")
EXPECTED_CHECKS = {"baseline", "line_grain", "correction", "late_sale", "customer_scd2",
                   "product_scd2", "historical_dimension_join", "soft_dq", "hard_reject",
                   "late_event", "replay", "reject_idempotency"}


def require_business_evidence(activity):
    """Fail closed when execution produced no complete fixture evidence."""
    evidence = json.loads(activity.get("output", {}).get("result", {}).get("exitValue") or "null")
    if (not evidence or evidence.get("status") != "passed"
            or set(evidence.get("checks", [])) != EXPECTED_CHECKS
            or evidence.get("source_mutations") != 0
            or evidence.get("ingestion_checkpoint_updates") != 0):
        raise RuntimeError("Notebook did not return all twelve isolated business acceptance checks")
    return evidence


def owned_item(api, config, name, kind, definition=None):
    """Create/reuse a fixture asset only when its ownership tag matches."""
    path = f"workspaces/{config['workspace_id']}/items"
    matches = [item for item in api.list_all(path) if item["displayName"] == name and item["type"] == kind]
    if len(matches) > 1:
        raise RuntimeError(f"Duplicate fixture item {name}")
    if matches:
        item = matches[0]
        if not item.get("description", "").startswith(OWNER):
            raise RuntimeError(f"Refusing unowned item {name}")
        if definition:
            api.call("POST", f"{path}/{item['id']}/updateDefinition", {"definition": definition})
        return item
    body = {"displayName": name, "type": kind,
            "description": OWNER + ": isolated Test-only business acceptance; no Production or real source writes."}
    if definition:
        body["definition"] = definition
    elif kind == "Lakehouse":
        body["creationPayload"] = {"enableSchemas": True}
    return api.call("POST", path, body)


def part(path, content):
    """Encode a native Fabric definition part without credentials."""
    return {"path": path, "payloadType": "InlineBase64",
            "payload": base64.b64encode(content.encode()).decode()}


def run_pipeline(api, workspace, item_id):
    """Submit once and poll the accepted job; never retry a write blindly."""
    token = api.credential.get_token("https://api.fabric.microsoft.com/.default").token
    path = f"workspaces/{workspace}/items/{item_id}"
    response = requests.post(f"{BASE}/{path}/jobs/Pipeline/instances",
                             headers={"Authorization": f"Bearer {token}"}, timeout=120)
    response.raise_for_status()
    job_path = urlparse(response.headers.get("Location", "")).path
    if response.status_code != 202 or not re.fullmatch(rf"/v1/{path}/jobs/instances/[a-fA-F0-9-]{{36}}", job_path):
        raise RuntimeError("Unexpected job response; inspect before resubmission")
    print(json.dumps({"status": "submitted", "job_id": job_path.rsplit("/", 1)[-1], "pipeline_id": item_id}), flush=True)
    deadline = time.monotonic() + 3600
    interval = max(int(response.headers.get("Retry-After", "30")), 1)
    while time.monotonic() < deadline:
        time.sleep(interval)
        job = api.call("GET", "https://api.fabric.microsoft.com" + job_path)
        if job["status"] in ("Completed", "Succeeded"):
            # Pipeline success alone is insufficient: an empty imported notebook
            # can succeed without executing any acceptance assertions.
            activities = api.call("POST", f"workspaces/{workspace}/datapipelines/pipelineruns/{job['id']}/queryactivityruns",
                                  {"filters": [], "lastUpdatedAfter": job["startTimeUtc"],
                                   "lastUpdatedBefore": job["endTimeUtc"]})["value"]
            matches = [activity for activity in activities if activity["activityName"] == "ValidateSilverBusinessContracts"]
            if len(matches) != 1 or matches[0]["status"] != "Succeeded":
                raise RuntimeError("Expected one successful business acceptance activity")
            job["business_evidence"] = require_business_evidence(matches[0])
            return job
        if job["status"] in ("Failed", "Cancelled", "Canceled", "Deduped"):
            raise RuntimeError(f"Acceptance job failed: {json.dumps(job)}")
    raise TimeoutError(f"Inspect running job {job_path}; do not resubmit blindly")


def consume(connection, sql):
    """Drain SQL result sets so deferred errors fail the acceptance run."""
    cursor = connection.execute(sql)
    while True:
        if cursor.description:
            cursor.fetchall()
        if not cursor.nextset():
            return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["test"], required=True)
    parser.add_argument("--execute", action="store_true", help="Create isolated fixtures and run bounded tests")
    args = parser.parse_args()
    config = json.loads((ROOT / "config/environments.json").read_text())[args.environment]
    if config["workspace_id"] != TEST_WORKSPACE or config["schedule_enabled"]:
        raise RuntimeError("Expected the unscheduled, isolated Test workspace")
    if not args.execute:
        print(json.dumps({"environment": "test", "mode": "plan", "assets": [
            "lh_cicd_acceptance_bronze", "lh_cicd_acceptance_silver", "wh_cicd_acceptance_gold",
            "nb_cicd_business_acceptance", "pl_cicd_business_acceptance"],
            "production_changes": 0, "source_changes": 0, "checkpoint_changes": 0}))
        return
    api = FabricAPI()
    inventory = api.list_all(f"workspaces/{TEST_WORKSPACE}/items")
    sources = {}
    for name in TRANSFORMS:
        item = next(item for item in inventory if item["displayName"] == name and item["type"] == "Notebook")
        definition = api.call("POST", f"workspaces/{TEST_WORKSPACE}/items/{item['id']}/getDefinition", {})
        content = next(block for block in definition["definition"]["parts"] if block["path"] == "notebook-content.py")
        sources[name] = base64.b64decode(content["payload"]).decode()
        if PRODUCTION in sources[name]:
            raise RuntimeError(f"Published {name} retains Production binding")
    bronze = owned_item(api, config, "lh_cicd_acceptance_bronze", "Lakehouse")
    silver = owned_item(api, config, "lh_cicd_acceptance_silver", "Lakehouse")
    gold = owned_item(api, config, "wh_cicd_acceptance_gold", "Warehouse")
    dependencies = {"kernel_info": {"name": "synapse_pyspark"}, "dependencies": {"lakehouse": {
        "default_lakehouse": silver["id"], "default_lakehouse_name": silver["displayName"],
        "default_lakehouse_workspace_id": TEST_WORKSPACE,
        "known_lakehouses": [{"id": silver["id"]}, {"id": bronze["id"]}]}}}
    metadata = "\n".join("# META " + line for line in json.dumps(dependencies, indent=2).splitlines())
    body = ("# Fabric notebook source\n\n# METADATA ********************\n\n" + metadata +
            "\n\n# MARKDOWN ********************\n\n# # Isolated Business Acceptance\n" +
            "# Executes published Silver transformations against a tiny owned fixture; asserts history, late arrivals, DQ and replay.\n" +
            "\n\n# CELL ********************\n\n" + f"WORKSPACE_ID = {TEST_WORKSPACE!r}\nBRONZE_ID = {bronze['id']!r}\n" +
            f"TRANSFORM_SOURCES = {sources!r}\n" + (ROOT / "deploy/business_fixture.py").read_text() +
            '\n# METADATA ********************\n\n# META {\n# META   "language": "python",\n# META   "language_group": "synapse_pyspark"\n# META }\n')
    notebook = owned_item(api, config, "nb_cicd_business_acceptance", "Notebook",
                          {"format": "fabricGitSource", "parts": [part("notebook-content.py", body)]})
    readback = api.call("POST", f"workspaces/{TEST_WORKSPACE}/items/{notebook['id']}/getDefinition", {})
    published = base64.b64decode(next(block for block in readback["definition"]["parts"]
                                     if block["path"] == "notebook-content.py")["payload"]).decode()
    if (ROOT / "deploy/business_fixture.py").read_text().strip() not in published:
        raise RuntimeError("Fabric notebook read-back does not contain the complete fixture code")
    pipeline_body = {"properties": {"concurrency": 1, "description": OWNER + ": isolated Spark business tests; no source ingestion.",
        "activities": [{"name": "ValidateSilverBusinessContracts", "type": "TridentNotebook", "dependsOn": [],
            "description": "Tests baseline, corrections, SCD2 as-of joins, late arrivals, DQ and replay using published transformation code.",
            "policy": {"timeout": "0.01:00:00", "retry": 0, "secureInput": False, "secureOutput": False},
            "typeProperties": {"notebookId": notebook["id"], "workspaceId": TEST_WORKSPACE}}]}}
    pipeline = owned_item(api, config, "pl_cicd_business_acceptance", "DataPipeline",
                          {"parts": [part("pipeline-content.json", json.dumps(pipeline_body))]})
    job = run_pipeline(api, TEST_WORKSPACE, pipeline["id"])
    # Use the published Gold SQL, retargeting only its Silver database identifier.
    deployed_gold = next(item for item in inventory if item["displayName"] == "pl_gold_orchestrator" and item["type"] == "DataPipeline")
    result = api.call("POST", f"workspaces/{TEST_WORKSPACE}/items/{deployed_gold['id']}/getDefinition", {})
    block = next(block for block in result["definition"]["parts"] if block["path"] == "pipeline-content.json")
    original = base64.b64decode(block["payload"]).decode()
    gold_definition = json.loads(original)
    activities = gold_definition["properties"]["activities"]
    if any(activity["type"] != "Script" for activity in activities):
        raise RuntimeError("Gold fixture runner requires explicit Script-only publication graph")
    with connect(api, TEST_WORKSPACE, gold["id"]) as connection:
        # Start with the reviewed Gold serving contract; publication compares
        # candidate schemas to these tables before its atomic data replacement.
        migrate(connection, ROOT / "migrations/wh_retail_gold")
        # SQL endpoint discovery is asynchronous after initial Spark table writes.
        ready = False
        for attempt in range(30):
            try:
                consume(connection, "SELECT TOP 1 1 FROM [lh_cicd_acceptance_silver].[conformed].[fact_order]")
                ready = True
                break
            except Exception as error:
                if attempt == 29:
                    raise RuntimeError("Fixture Silver SQL endpoint did not synchronize") from error
                time.sleep(20)
        if not ready:
            raise RuntimeError("Fixture SQL endpoint unavailable")
        completed = set()
        pending = list(activities)
        while pending:
            eligible = [activity for activity in pending if all(
                dependency["activity"] in completed for dependency in activity.get("dependsOn", []))]
            if not eligible:
                raise RuntimeError("Unresolvable Gold dependency graph")
            for activity in eligible:
                for script in activity["typeProperties"]["scripts"]:
                    if not isinstance(script["text"], str):
                        raise RuntimeError("Dynamic Gold SQL requires a reviewed runner")
                    sql = script["text"].replace("[lh_retail_silver]", "[lh_cicd_acceptance_silver]")
                    consume(connection, sql)
                completed.add(activity["name"])
                pending.remove(activity)
                print(json.dumps({"gold_activity": activity["name"], "status": "passed"}), flush=True)
        audit = connection.execute("SELECT eligible_gross_booked_sales_amount, eligible_sales_line_count, sales_line_count, order_count FROM gold.kpi_audit").fetchall()
        if len(audit) != 1 or tuple(audit[0]) != (230, 4, 5, 4):
            raise RuntimeError(f"Gold fixture totals differ: {audit}")
    report = {"status": "passed", "scope": "isolated_silver_gold_business_acceptance",
              "environment": "test", "spark_job_id": job["id"], "gold_activities": sorted(completed),
              "silver_checks": job["business_evidence"],
              "gold_sql_definition_sha256": hashlib.sha256(original.encode()).hexdigest(),
              "eligible_gross_sales": "230.00", "eligible_lines": 4, "sales_lines": 5, "orders": 4,
              "source_mutations": 0, "ingestion_checkpoint_updates": 0,
              "assets": {item["displayName"]: item["id"] for item in (bronze, silver, gold, notebook, pipeline)},
              "limitations": ["fixture landing is not a source Copy test", "Gold SQL executed by the authenticated test runner, not a pipeline job", "semantic serving not tested"]}
    output = ROOT / "output/business_acceptance.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
