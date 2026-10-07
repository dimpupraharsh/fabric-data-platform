"""Compare published semantic measures with isolated Test Gold audit totals.

This operator-only check copies the published model to one ownership-tagged Test
fixture and rebinds its datasource solely to the acceptance Warehouse. It does
not update the retail model, Production, sources, checkpoints or schedules.
SSO-enabled models require delegated operator authentication for executeQueries;
do not add this script as a service-principal CI gate or bypass SSO/RLS.
"""

import argparse
import base64
from decimal import Decimal
import json
from pathlib import Path

import requests

from export_sql_schema import connect
from fabric_api import FabricAPI
from test_business_acceptance import OWNER, PRODUCTION, TEST_WORKSPACE, owned_item, part

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("Sales", "Lines", "Orders", "SLA")
QUERY = ('EVALUATE ROW("Sales", [Gross Booked Sales], "Lines", [Sales Lines], '
         '"Orders", [Eligible Orders], "SLA", [SLA Eligible Deliveries])')


def query_totals(payload):
    """Reject nested API errors and malformed result sets, including HTTP 200 errors."""
    results = payload.get("results", [])
    if payload.get("error") or len(results) != 1 or results[0].get("error"):
        raise RuntimeError(f"Semantic query failed: {payload}")
    tables = results[0].get("tables", [])
    if len(tables) != 1 or tables[0].get("error") or len(tables[0].get("rows", [])) != 1:
        raise RuntimeError("Expected one semantic result row")
    row = tables[0]["rows"][0]
    if set(row) != {f"[{name}]" for name in NAMES}:
        raise RuntimeError("Semantic result is missing a certified measure")
    return {name: Decimal(str(row[f"[{name}]"])) for name in NAMES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["test"], required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"mode": "plan", "environment": "test", "asset": "sm_cicd_business_acceptance",
                          "source_changes": 0, "checkpoint_changes": 0, "production_changes": 0}))
        return
    config = json.loads((ROOT / "config/environments.json").read_text())["test"]
    if config["workspace_id"] != TEST_WORKSPACE or config["schedule_enabled"]:
        raise RuntimeError("Expected isolated, unscheduled Test workspace")
    api = FabricAPI()
    inventory = api.list_all(f"workspaces/{TEST_WORKSPACE}/items")
    gold = next(item for item in inventory if item["type"] == "Warehouse"
                and item["displayName"] == "wh_cicd_acceptance_gold")
    if not gold.get("description", "").startswith(OWNER):
        raise RuntimeError("Refusing unowned Gold fixture")
    with connect(api, TEST_WORKSPACE, gold["id"]) as connection:
        rows = connection.execute("SELECT eligible_gross_booked_sales_amount, eligible_sales_line_count, "
                                  "eligible_order_count, shipping_sla_eligible_order_count FROM gold.kpi_audit").fetchall()
    if len(rows) != 1 or tuple(rows[0]) != (230, 4, 4, 2):
        raise RuntimeError(f"Complete business fixture required before semantic test: {rows}")
    expected = dict(zip(NAMES, map(Decimal, rows[0])))
    model_id = config["item_ids"]["SemanticModel/sm_retail_order_intelligence"]
    source_gold = config["item_ids"]["Warehouse/wh_retail_gold"]
    deployed = api.call("POST", f"workspaces/{TEST_WORKSPACE}/items/{model_id}/getDefinition", {})
    parts = []
    replacements = 0
    for block in deployed["definition"]["parts"]:
        if block["path"] == ".platform":
            continue
        content = base64.b64decode(block["payload"]).decode()
        if PRODUCTION in content:
            raise RuntimeError("Published Test model retains Production workspace binding")
        replacements += content.count(source_gold)
        parts.append(part(block["path"], content.replace(source_gold, gold["id"])))
    if replacements != 1:
        raise RuntimeError("Expected exactly one explicit Test Gold datasource binding")
    model = owned_item(api, config, "sm_cicd_business_acceptance", "SemanticModel", {"parts": parts})
    token = api.credential.get_token("https://analysis.windows.net/powerbi/api/.default").token
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{TEST_WORKSPACE}/datasets/{model['id']}"
    headers = {"Authorization": f"Bearer {token}"}
    datasource_response = requests.get(url + "/datasources", headers=headers, timeout=120)
    datasource_response.raise_for_status()
    datasources = datasource_response.json().get("value", [])
    if len(datasources) != 1 or datasources[0].get("connectionDetails", {}).get("database") != gold["id"]:
        raise RuntimeError("Live semantic datasource is not the acceptance Gold Warehouse")
    response = requests.post(url + "/executeQueries", headers=headers,
                             json={"queries": [{"query": QUERY}]}, timeout=120)
    response.raise_for_status()
    actual = query_totals(response.json())
    if actual != expected:
        raise RuntimeError(f"Semantic totals disagree with isolated Gold audit: {actual} != {expected}")
    report = {"status": "passed", "scope": "delegated_operator_isolated_semantic_acceptance",
              "workspace_id": TEST_WORKSPACE, "model_id": model["id"], "gold_id": gold["id"],
              "totals": {name: str(value) for name, value in actual.items()},
              "source_changes": 0, "checkpoint_changes": 0, "production_changes": 0,
              "limitations": "Operator-authenticated measure query, not a service-principal SSO CI gate"}
    output = ROOT / "output/semantic_acceptance.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
