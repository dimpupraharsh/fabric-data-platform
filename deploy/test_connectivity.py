"""Run a bounded Fabric connector test in Dev/Test only.

The PostgreSQL gateway executes SELECT constants, copying one synthetic probe
row into ci_connectivity_probe in the selected non-production Bronze Lakehouse.
Four S3 GetMetadata activities check approved reference paths without replacing
files. SQL Script checks the selected control Warehouse. No operational source
rows, ingestion checkpoints, Production destinations or schedules are changed.
"""

import argparse
import base64
import copy
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse
from uuid import uuid4

import requests

from fabric_api import BASE, FabricAPI

ROOT = Path(__file__).resolve().parents[1]
NAME = "pl_cicd_connectivity_probe"


def definition(config, items):
    """Construct a test pipeline from proven connector shapes, not saved secrets."""
    bronze = next(item for item in items if item["type"] == "Lakehouse" and item["displayName"] == "lh_retail_bronze")
    watermark = json.loads((ROOT / "workspace/pl_bronze_pg_watermark.DataPipeline/pipeline-content.json").read_text())
    pg_dataset = copy.deepcopy(watermark["properties"]["activities"][0]["typeProperties"]["datasetSettings"])
    pg_dataset["typeProperties"] = {"schema": "retail_oi", "table": "customer_master"}
    pg_dataset["externalReferences"]["connection"] = config["connections"]["e3607aae-ab0a-4954-968c-613ebd192eeb"]
    snapshot = json.loads((ROOT / "workspace/pl_bronze_s3_snapshot.DataPipeline/pipeline-content.json").read_text())
    template = snapshot["properties"]["activities"][1]["typeProperties"]
    sink = copy.deepcopy(template["sink"])
    destination = sink["datasetSettings"]["connectionSettings"]["properties"]
    destination["typeProperties"].update({"workspaceId": config["workspace_id"], "artifactId": bronze["id"]})
    destination["externalReferences"]["connection"] = config["connections"]["aedad88b-3c1c-470e-8f95-bfafb37f40c5"]
    sink["datasetSettings"]["typeProperties"]["table"] = "ci_connectivity_probe"
    policy = {"timeout": "0.00:05:00", "retry": 0, "secureInput": False, "secureOutput": False}
    activities = [{"name": "ProbePostgreSQLToNonproductionLakehouse", "type": "Copy", "dependsOn": [],
                   "description": "Copies one synthetic constant row through the gateway; no business table scan or checkpoint update.",
                   "policy": policy, "typeProperties": {
                       "source": {"type": "PostgreSqlSource", "partitionOption": "None", "queryTimeout": "00:05:00",
                                  "query": f"SELECT '{uuid4()}'::text AS ci_run_id, 1::integer AS probe_ok, CURRENT_TIMESTAMP AS probe_ts",
                                  "datasetSettings": pg_dataset},
                       "sink": sink, "enableStaging": False, "translator": {"type": "TabularTranslator", "typeConversion": True}}}]
    metadata_names = []
    for name in ("location_master", "delivery_zone_lookup", "warehouse_coverage", "geo_hierarchy"):
        dataset = copy.deepcopy(template["source"]["datasetSettings"])
        dataset["typeProperties"]["location"] = {"type": "AmazonS3Location", "bucketName": "fabric-datawarehouse-project",
                                                 "folderPath": f"retail_ref/{name}", "fileName": f"{name}.csv"}
        dataset["externalReferences"]["connection"] = config["connections"]["2977a806-dd08-4233-b4d1-bd1521ec0d16"]
        activity_name = "Check_" + name
        metadata_names.append(activity_name)
        activities.append({"name": activity_name, "type": "GetMetadata", "dependsOn": [], "policy": policy,
                           "description": f"Checks existence of the approved S3 {name}.csv object without refreshing it.",
                           "typeProperties": {"datasetSettings": dataset, "fieldList": ["exists"],
                                              "storeSettings": {"type": "AmazonS3ReadSettings"},
                                              "formatSettings": {"type": "DelimitedTextReadSettings"}}})
    conditions = [f"equals(activity('{name}').output.exists, true)" for name in metadata_names]
    expression = conditions[0]
    for condition in conditions[1:]:
        expression = f"and({expression}, {condition})"
    activities.append({"name": "RequireAllS3References", "type": "IfCondition",
                       "description": "Fails the release probe when any required enrichment file is missing.",
                       "dependsOn": [{"activity": name, "dependencyConditions": ["Succeeded"]} for name in metadata_names],
                       "typeProperties": {"expression": {"value": "@" + expression, "type": "Expression"},
                                          "ifTrueActivities": [], "ifFalseActivities": [{"name": "MissingReferenceFile",
                                              "type": "Fail", "description": "Reports a missing S3 reference as a release blocker.",
                                              "typeProperties": {"message": "A required S3 reference file is missing", "errorCode": "S3_REFERENCE_MISSING"}}]}})
    orchestrator = json.loads((ROOT / "workspace/pl_bronze_orchestrator.DataPipeline/pipeline-content.json").read_text())
    scripts = [activity for activity in orchestrator["properties"]["activities"] if activity["type"] == "Script"]
    lookup = copy.deepcopy(scripts[0])
    lookup["name"] = "ProbeControlWarehouse"
    lookup["description"] = "Reads a constant from the isolated control Warehouse using its workspace-identity connector."
    lookup["dependsOn"] = []
    lookup["policy"] = policy
    lookup["typeProperties"]["scripts"] = [{"type": "Query", "text": "SELECT 1 AS probe_ok"}]
    # All static Warehouse bindings in this test lookup resolve to the target environment.
    def rebind(value):
        if isinstance(value, dict):
            return {key: rebind(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rebind(item) for item in value]
        if isinstance(value, str):
            for source, target in config["connections"].items():
                value = value.replace(source, target)
            control = next(item for item in items if item["type"] == "Warehouse" and item["displayName"] == "wh_retail_control")
            value = value.replace("fba1bab2-0098-4b65-9f4f-cb304d71b700", config["workspace_id"])
            value = value.replace("c8dbe07a-2181-4c0c-bec9-b7719017bb9f", control["id"])
        return value
    activities.append(rebind(lookup))
    return {"properties": {"description": __doc__.strip(), "activities": activities}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["dev", "test"], required=True)
    args = parser.parse_args()
    config = json.loads((ROOT / "config/environments.json").read_text())[args.environment]
    api = FabricAPI()
    path = f"workspaces/{config['workspace_id']}/items"
    items = api.list_all(path)
    content = definition(config, items)
    # Fail before submitting if a generated test definition retains a Production destination.
    serialized = json.dumps(content)
    forbidden = ["fba1bab2-0098-4b65-9f4f-cb304d71b700", "ed2e34f8-b837-43c6-b6ba-de68cd7e0079",
                 "c8dbe07a-2181-4c0c-bec9-b7719017bb9f", "aedad88b-3c1c-470e-8f95-bfafb37f40c5",
                 "ffb74af9-9d17-4429-8493-02465e631244"]
    if any(identifier in serialized for identifier in forbidden):
        raise RuntimeError("Generated probe contains a Production destination")
    payload = {"parts": [{"path": "pipeline-content.json", "payloadType": "InlineBase64",
                           "payload": base64.b64encode(serialized.encode()).decode()}]}
    matches = [item for item in items if item["type"] == "DataPipeline" and item["displayName"] == NAME]
    if len(matches) > 1:
        raise RuntimeError("Duplicate test pipeline names")
    if matches:
        item = matches[0]
        api.call("POST", f"{path}/{item['id']}/updateDefinition", {"definition": payload})
    else:
        item = api.call("POST", path, {"displayName": NAME, "type": "DataPipeline", "description": "Nonproduction-only CI connector probe. Copies one synthetic row through PostgreSQL gateway; checks four approved S3 files and control SQL. No ingestion checkpoints or Production changes.",
                                      "definition": payload})
    token = api.credential.get_token("https://api.fabric.microsoft.com/.default").token
    response = requests.post(f"{BASE}/{path}/{item['id']}/jobs/Pipeline/instances",
                             headers={"Authorization": f"Bearer {token}"}, timeout=120)
    response.raise_for_status()
    if response.status_code != 202:
        raise RuntimeError("Expected an accepted pipeline execution")
    location = response.headers.get("Location", "")
    job_path = urlparse(location).path
    expected = rf"/v1/{path}/{item['id']}/jobs/instances/[0-9a-fA-F-]{{36}}"
    if not re.fullmatch(expected, job_path):
        raise RuntimeError("Unexpected job polling URL; refusing to forward a token")
    print(json.dumps({"status": "submitted", "environment": args.environment, "pipeline_id": item["id"],
                      "job_id": job_path.rsplit("/", 1)[-1]}), flush=True)
    time.sleep(max(int(response.headers.get("Retry-After", "30")), 1))
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        job = api.call("GET", "https://api.fabric.microsoft.com" + job_path)
        if job["status"] in ("Completed", "Succeeded"):
            print(json.dumps({"status": "passed", "scope": "bounded_connector_probe_only", "environment": args.environment,
                              "pipeline_id": item["id"], "job_id": job.get("id"), "synthetic_rows_expected": 1,
                              "source_files_checked": 4, "checkpoint_updates": 0}))
            return
        if job["status"] in ("Failed", "Cancelled", "Canceled", "Deduped"):
            raise RuntimeError(f"Connector probe did not succeed: {json.dumps(job)}")
        time.sleep(30)
    raise TimeoutError("Connector probe exceeded 15 minutes; inspect its existing run before submitting again")


if __name__ == "__main__":
    main()
