"""Fault-inject cleanup/failure propagation in isolated Test pipelines.

Copies the reviewed Fail activities and parent invocation shape. SQL statements
are replaced with constants or deliberate divide-by-zero errors. No source,
business table, checkpoint or schedule writes occur. This tests pipeline outcome
semantics, not the real Copy/manifest path or real lease cleanup procedures.
"""

import argparse
import base64
import copy
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse

import requests

from fabric_api import BASE, FabricAPI
from test_business_acceptance import TEST_WORKSPACE, owned_item, part

ROOT = Path(__file__).resolve().parents[1]


def scopes(activities):
    """Find nested activity scopes while retaining their branch dependencies."""
    yield activities
    for activity in activities:
        properties = activity.get("typeProperties", {})
        for key in ("activities", "ifTrueActivities", "ifFalseActivities"):
            yield from scopes(properties.get(key, []))


def require_child_failures(api, activities, query, cleanup_fails):
    """Check the intended failure, not an unrelated authentication/config error."""
    evidence = {}
    for activity in activities:
        if activity["activityName"] == "GoldMustNotRun":
            continue
        run_id = activity.get("output", {}).get("pipelineRunId")
        if not run_id:
            raise RuntimeError("Failed child invocation did not expose its run ID")
        children = api.call("POST", f"workspaces/{TEST_WORKSPACE}/datapipelines/pipelineruns/{run_id}/queryactivityruns", query)["value"]
        statuses = {child["activityName"]: child["status"] for child in children}
        cleanup = "FailAfterCountBoundedSourceRows" if activity["activityName"] == "BronzeFailureChild" else "LogDimensionsFailure"
        upstream = "CountBoundedSourceRows" if activity["activityName"] == "BronzeFailureChild" else "BuildSilverDimensionsAndBridges"
        if statuses != {upstream: "Failed", cleanup: "Failed" if cleanup_fails else "Succeeded", "Propagate" + cleanup: "Failed"}:
            raise RuntimeError(f"Wrong child failure path: {statuses}")
        failure = next(child for child in children if child["activityName"] == "Propagate" + cleanup)
        if failure.get("error", {}).get("errorCode") != "RETAIL_UPSTREAM_ACTIVITY_FAILED":
            raise RuntimeError(f"Child failed for an unexpected reason: {failure.get('error')}")
        evidence[activity["activityName"]] = {"job_id": run_id, "activities": statuses,
                                             "error_code": "RETAIL_UPSTREAM_ACTIVITY_FAILED"}
    if len(evidence) != 2:
        raise RuntimeError("Expected two proven child failure paths")
    return evidence


def submit_and_expect_failure(api, item_id, cleanup_fails):
    """Submit once and require a failed parent with skipped downstream serving."""
    path = f"workspaces/{TEST_WORKSPACE}/items/{item_id}"
    token = api.credential.get_token("https://api.fabric.microsoft.com/.default").token
    response = requests.post(f"{BASE}/{path}/jobs/Pipeline/instances",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"executionData": {"parameters": {"cleanup_fails": cleanup_fails}}}, timeout=120)
    response.raise_for_status()
    location = urlparse(response.headers.get("Location", "")).path
    if response.status_code != 202 or not re.fullmatch(rf"/v1/{path}/jobs/instances/[a-fA-F0-9-]{{36}}", location):
        raise RuntimeError("Unexpected accepted job response; inspect before resubmission")
    print(json.dumps({"submitted_job": location.rsplit("/", 1)[-1], "cleanup_fails": cleanup_fails}), flush=True)
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        time.sleep(30)
        job = api.call("GET", "https://api.fabric.microsoft.com" + location)
        if job["status"] in ("NotStarted", "InProgress"):
            continue
        if job["status"] != "Failed":
            raise RuntimeError(f"Failure fixture did not fail: {job}")
        query = {"filters": [], "lastUpdatedAfter": job["startTimeUtc"], "lastUpdatedBefore": job["endTimeUtc"]}
        activities = api.call("POST", f"workspaces/{TEST_WORKSPACE}/datapipelines/pipelineruns/{job['id']}/queryactivityruns", query)["value"]
        statuses = {activity["activityName"]: activity["status"] for activity in activities}
        # Fabric can omit a never-started skipped activity from queryactivityruns.
        # Absence is accepted only for the published success-dependent sentinel.
        if statuses.get("GoldMustNotRun") not in (None, "Skipped"):
            raise RuntimeError("Downstream Gold sentinel executed after a failed child")
        statuses.setdefault("GoldMustNotRun", "NotExecuted")
        if (statuses.get("BronzeFailureChild") != "Failed"
                or statuses.get("SilverFailureChild") != "Failed" or len(statuses) != 3):
            raise RuntimeError(f"Unexpected parent activity outcomes: {statuses}")
        child_evidence = require_child_failures(api, activities, query, cleanup_fails)
        return {"job_id": job["id"], "cleanup_fails": cleanup_fails, "parent_status": "Failed",
                "activities": statuses, "children": child_evidence}
    raise TimeoutError(f"Inspect existing fault-injection job {location}; do not resubmit blindly")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["test"], required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"mode": "plan", "environment": "test", "source_changes": 0, "checkpoint_changes": 0}))
        return
    config = json.loads((ROOT / "config/environments.json").read_text())["test"]
    if config["workspace_id"] != TEST_WORKSPACE or config["schedule_enabled"]:
        raise RuntimeError("Expected unscheduled Test workspace")
    api = FabricAPI()
    sql_template = json.loads((ROOT / "workspace/pl_silver_orchestrator.DataPipeline/pipeline-content.json").read_text())["properties"]["activities"][0]

    def sql_activity(name, text, dependencies):
        """Use the known connector shape, rebinding solely to Test control SQL."""
        activity = copy.deepcopy(sql_template)
        activity.update(name=name, description="Constant-only failure propagation fixture; no data or control-state writes.", dependsOn=dependencies)
        activity["typeProperties"]["scripts"] = [{"type": "Query", "text": text}]
        activity["policy"]["retry"] = 0
        activity["externalReferences"]["connection"] = config["connections"]["ffb74af9-9d17-4429-8493-02465e631244"]
        return activity

    children = []
    for layer, pipeline, cleanup_name in (("Bronze", "pl_bronze_pg_watermark", "FailAfterCountBoundedSourceRows"),
                                          ("Silver", "pl_silver_orchestrator", "LogDimensionsFailure")):
        definition = json.loads((ROOT / f"workspace/{pipeline}.DataPipeline/pipeline-content.json").read_text())
        group = next(group for group in scopes(definition["properties"]["activities"])
                     if any(activity["name"] == cleanup_name for activity in group))
        cleanup = next(activity for activity in group if activity["name"] == cleanup_name)
        upstream = cleanup["dependsOn"][0]["activity"]
        propagate = copy.deepcopy(next(activity for activity in group if activity["name"] == "Propagate" + cleanup_name))
        activities = [sql_activity(upstream, "SELECT 1 / 0 AS deliberate_failure", []),
                      sql_activity(cleanup_name, {"value": "@if(pipeline().parameters.cleanup_fails, 'SELECT 1 / 0 AS cleanup_failure', 'SELECT 1 AS cleanup_ok')", "type": "Expression"},
                                   [{"activity": upstream, "dependencyConditions": ["Failed"]}]), propagate]
        body = {"properties": {"concurrency": 1, "description": __doc__.strip(),
                                "parameters": {"cleanup_fails": {"type": "Bool", "defaultValue": False}}, "activities": activities}}
        child = owned_item(api, config, f"pl_cicd_failure_{layer.lower()}", "DataPipeline",
                           {"parts": [part("pipeline-content.json", json.dumps(body))]})
        children.append((layer, child))
    template = json.loads((ROOT / "workspace/pl_daily_retail_processing.DataPipeline/pipeline-content.json").read_text())["properties"]["activities"][0]
    invocations = []
    for layer, child in children:
        invocation = copy.deepcopy(template)
        invocation.update(name=layer + "FailureChild", dependsOn=[], description="Waits for the deliberately failed child; serving must not execute.")
        invocation["typeProperties"]["pipeline"]["referenceName"] = child["id"]
        invocation["typeProperties"]["parameters"] = {"cleanup_fails": {"value": "@pipeline().parameters.cleanup_fails", "type": "Expression"}}
        invocations.append(invocation)
    invocations.append(sql_activity("GoldMustNotRun", "SELECT 1 AS unexpected_serving",
                                   [{"activity": activity["name"], "dependencyConditions": ["Succeeded"]} for activity in invocations]))
    parent = owned_item(api, config, "pl_cicd_failure_parent", "DataPipeline", {"parts": [part("pipeline-content.json", json.dumps({
        "properties": {"concurrency": 1, "description": __doc__.strip(),
                       "parameters": {"cleanup_fails": {"type": "Bool", "defaultValue": False}}, "activities": invocations}}))]})
    readback = api.call("POST", f"workspaces/{TEST_WORKSPACE}/items/{parent['id']}/getDefinition", {})
    published = json.loads(base64.b64decode(next(block for block in readback["definition"]["parts"]
                                               if block["path"] == "pipeline-content.json")["payload"]))
    sentinel = next(activity for activity in published["properties"]["activities"] if activity["name"] == "GoldMustNotRun")
    if sentinel["dependsOn"] != invocations[-1]["dependsOn"]:
        raise RuntimeError("Failure fixture read-back lost its success-dependent Gold sentinel")
    results = [submit_and_expect_failure(api, parent["id"], value) for value in (False, True)]
    report = {"status": "passed", "scope": "isolated_failure_propagation_pattern", "runs": results,
              "source_changes": 0, "checkpoint_changes": 0, "production_changes": 0,
              "limitations": "Does not exercise actual Copy, manifest, notebook failures or lease cleanup SQL"}
    output = ROOT / "output/failure_acceptance.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
