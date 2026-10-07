"""Grant only connection-user access to each non-production deployment/runtime identity.

Run once with the connection owner, not from application CI. No ownership,
resharing, tenant-wide permission, or Production write connector is granted.
Shared PostgreSQL/S3 credentials remain a portfolio exception: User access to
a connector does not make its underlying database or IAM credential read-only.
"""

import argparse
import json
from pathlib import Path

from fabric_api import FabricAPI

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["dev", "test"], required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "config/environments.json").read_text())[args.environment]
    production = json.loads((ROOT / "config/environments.json").read_text())["production"]
    forbidden = set(production["connections"].values()) - set(config["shared_read_connections"])
    api = FabricAPI()
    principals = {config["deployment_principal_id"], config["runtime_principal_id"]}
    for connection_id in sorted(set(config["connections"].values())):
        if connection_id in forbidden:
            raise RuntimeError("Refusing to grant access to a Production write connector")
        existing = api.list_all(f"connections/{connection_id}/roleAssignments")
        for principal_id in sorted(principals):
            matches = [row for row in existing if row["principal"]["id"] == principal_id]
            if matches:
                print(json.dumps({"connection_id": connection_id, "principal_id": principal_id,
                                  "status": "existing", "role": matches[0]["role"]}))
                continue
            if args.execute:
                api.call("POST", f"connections/{connection_id}/roleAssignments", {
                    "principal": {"id": principal_id, "type": "ServicePrincipal"}, "role": "User"})
                verified = api.list_all(f"connections/{connection_id}/roleAssignments")
                if not any(row["principal"]["id"] == principal_id and row["role"] == "User" for row in verified):
                    raise RuntimeError("Connection permission read-back failed")
            print(json.dumps({"connection_id": connection_id, "principal_id": principal_id,
                              "status": "granted" if args.execute else "planned", "role": "User"}))


if __name__ == "__main__":
    main()
