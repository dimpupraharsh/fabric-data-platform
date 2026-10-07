"""Create distinct Dev/Test Warehouse connections using workspace identity.

The PostgreSQL gateway and S3 connections are explicitly shared as read sources
for this controlled portfolio dataset. Production SQL write connections are never
shared. Lakehouse OAuth connections require an interactive Fabric bootstrap;
this script does not copy/export saved credentials or bypass sign-in.
"""

import argparse
import json
from pathlib import Path

from fabric_api import FabricAPI

ROOT = Path(__file__).resolve().parents[1]
SOURCE_READ_CONNECTIONS = ["e3607aae-ab0a-4954-968c-613ebd192eeb", "2977a806-dd08-4233-b4d1-bd1521ec0d16"]
SQL_CONNECTIONS = {"wh_retail_control": "ffb74af9-9d17-4429-8493-02465e631244", "wh_retail_gold": "0a85b5ac-b0d0-4686-9de2-c3bf62dac800"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["dev", "test"], required=True)
    args = parser.parse_args()
    path = ROOT / "config/environments.json"
    configurations = json.loads(path.read_text())
    config = configurations[args.environment]
    api = FabricAPI()
    existing = api.list_all("connections")
    items = api.list_all(f"workspaces/{config['workspace_id']}/items")
    for name, source_id in SQL_CONNECTIONS.items():
        item = next(x for x in items if x["displayName"] == name and x["type"] == "Warehouse")
        warehouse = api.call("GET", f"workspaces/{config['workspace_id']}/warehouses/{item['id']}")
        server = warehouse["properties"]["connectionString"]
        display_name = f"conn_{args.environment}_sql_{name}_workspace_identity"
        matches = [x for x in existing if x["displayName"] == display_name]
        if matches:
            assert len(matches) == 1
            connection = matches[0]
            assert connection["connectionDetails"]["path"].lower() == f"{server};{name}".lower()
        else:
            connection = api.call("POST", "connections", {
                "connectivityType": "ShareableCloud", "displayName": display_name,
                "connectionDetails": {"type": "SQL", "creationMethod": "Sql", "parameters": [
                    {"dataType": "Text", "name": "server", "value": server},
                    {"dataType": "Text", "name": "database", "value": name}]},
                "privacyLevel": "Organizational", "credentialDetails": {
                    "singleSignOnType": "None", "connectionEncryption": "Encrypted",
                    "skipTestConnection": False, "credentials": {"credentialType": "WorkspaceIdentity"}}})
        config["connections"][source_id] = connection["id"]
        print(json.dumps({"environment": args.environment, "connection": display_name, "id": connection["id"]}))
    config["shared_read_connections"] = SOURCE_READ_CONNECTIONS
    for identifier in SOURCE_READ_CONNECTIONS:
        config["connections"][identifier] = identifier
    lakehouse_id = config["connections"].get("aedad88b-3c1c-470e-8f95-bfafb37f40c5")
    if lakehouse_id and lakehouse_id != "aedad88b-3c1c-470e-8f95-bfafb37f40c5":
        # Gateway-backed PostgreSQL copies must be allowed to use this cloud sink.
        lakehouse = api.call("GET", f"connections/{lakehouse_id}")
        if lakehouse["connectionDetails"]["type"] != "Lakehouse":
            raise RuntimeError("Configured Lakehouse sink has an unexpected connector type")
        if not lakehouse.get("allowConnectionUsageInGateway", False):
            api.call("PATCH", f"connections/{lakehouse_id}", {
                "connectivityType": "ShareableCloud", "allowConnectionUsageInGateway": True})
        verified = api.call("GET", f"connections/{lakehouse_id}")
        if not verified.get("allowConnectionUsageInGateway", False):
            raise RuntimeError("Lakehouse gateway usage was not enabled")
    path.write_text(json.dumps(configurations, indent=2) + "\n")


if __name__ == "__main__":
    main()
