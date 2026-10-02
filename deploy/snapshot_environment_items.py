"""Export only item-name/ID metadata for cross-environment release isolation checks.

Use the authorized operator after bootstrap or item creation. This does not
export definitions, credentials, business data or runtime checkpoint contents.
Application CI uses the reviewed snapshot instead of reading other workspaces.
"""

import json
from pathlib import Path

from fabric_api import FabricAPI

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "config/environments.json"
    configurations = json.loads(path.read_text())
    api = FabricAPI()
    for environment, config in configurations.items():
        items = api.list_all(f"workspaces/{config['workspace_id']}/items")
        mapping = {}
        for item in items:
            key = item["type"] + "/" + item["displayName"]
            if key in mapping:
                raise RuntimeError(f"Duplicate named item in {environment}: {key}")
            mapping[key] = item["id"]
        config["item_ids"] = mapping
        print(json.dumps({"environment": environment, "metadata_items": len(mapping)}))
    path.write_text(json.dumps(configurations, indent=2) + "\n")


if __name__ == "__main__":
    main()
