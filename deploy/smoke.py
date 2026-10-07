"""Read-only OIDC/SQL readiness probe; this never starts ingestion or changes state.

The foundation probe checks isolated workspace identity and both Warehouse
schemas. Application mode additionally checks expected deployed item names.
This is a deployment smoke test, not evidence of an end-to-end data processing run.
"""

import argparse
import json
from pathlib import Path

from export_sql_schema import connect
from fabric_api import FabricAPI

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["dev", "test", "production"], required=True)
    parser.add_argument("--application", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "config/environments.json").read_text())[args.environment]
    api = FabricAPI()
    workspace = api.call("GET", f"workspaces/{config['workspace_id']}")
    assert workspace["id"] == config["workspace_id"]
    items = api.list_all(f"workspaces/{config['workspace_id']}/items")
    results = {}
    for name, schema, expected in (("wh_retail_control", "control", 16), ("wh_retail_gold", "gold", 20)):
        item = next(x for x in items if x["displayName"] == name and x["type"] == "Warehouse")
        with connect(api, config["workspace_id"], item["id"]) as connection:
            count = connection.execute("SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE s.name=?", schema).fetchone()[0]
            assert count >= expected, f"{name}: expected {expected} tables, found {count}"
            results[name] = count
    if args.application:
        inventory = json.loads((ROOT / "config/source_inventory.json").read_text())
        expected_items = {(x["name"], x["type"]) for x in inventory["items"]}
        actual = {(x["displayName"], x["type"]) for x in items}
        assert not expected_items - actual, f"Missing: {expected_items - actual}"
    print(json.dumps({"status": "passed", "scope": "deployment_smoke_only", "environment": args.environment, "workspace_id": workspace["id"], "warehouse_table_counts": results}))


if __name__ == "__main__":
    main()
