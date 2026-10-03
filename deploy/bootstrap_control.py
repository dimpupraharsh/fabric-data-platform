"""Seed non-production control metadata without importing Production runtime state.

Only approved configuration tables are copied. Connection IDs/names are rebound,
sources start disabled, and load/transform checkpoints are initialized empty.
Existing target rows are left unchanged so reruns cannot reset checkpoints.
Production execution is explicitly forbidden.
"""

import argparse
import datetime
import json
from pathlib import Path

from export_sql_schema import connect, quote
from fabric_api import FabricAPI

ROOT = Path(__file__).resolve().parents[1]
CONFIG_TABLES = ("ctl_source_system", "ctl_connection", "ctl_source_object", "ctl_schema_contract", "ctl_transform_object")


def export_metadata():
    """Read configuration only; never select transactional data or control logs."""
    api = FabricAPI()
    inventory = json.loads((ROOT / "config/source_inventory.json").read_text())
    item = next(x for x in inventory["items"] if x["name"] == "wh_retail_control")
    output = {}
    with connect(api, inventory["source_workspace_id"], item["source_id"]) as connection:
        for table in CONFIG_TABLES:
            cursor = connection.execute(f"SELECT * FROM control.{quote(table)}")
            columns = [x[0] for x in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            # Metadata timestamps are deployment-local; connection GUIDs are not credentials.
            for row in rows:
                for key in list(row):
                    if key.startswith("dwh_") and key.endswith("ts"):
                        row.pop(key)
            output[table] = rows
    path = ROOT / "config/control_seed.json"
    path.write_text(json.dumps(output, indent=2, default=lambda value: value.isoformat() if isinstance(value, (datetime.date, datetime.datetime)) else str(value)) + "\n")
    print(json.dumps({"exported_configuration_rows": {name: len(rows) for name, rows in output.items()}}))


def bootstrap(environment):
    """Insert missing metadata using bound connectors; never alter existing state."""
    if environment == "production":
        raise RuntimeError("Production bootstrap is forbidden; use explicit reviewed metadata migrations")
    config = json.loads((ROOT / "config/environments.json").read_text())[environment]
    data = json.loads((ROOT / "config/control_seed.json").read_text())
    api = FabricAPI()
    item = next(x for x in api.list_all(f"workspaces/{config['workspace_id']}/items") if x["type"] == "Warehouse" and x["displayName"] == "wh_retail_control")
    with connect(api, config["workspace_id"], item["id"]) as connection:
        connection.autocommit = False
        try:
            for table in CONFIG_TABLES:
                identity = "schema_contract_key" if table == "ctl_schema_contract" else {
                    "ctl_source_system": "source_system_id", "ctl_connection": "connection_id",
                    "ctl_source_object": "source_object_id", "ctl_transform_object": "transform_object_id"}[table]
                for source_row in data[table]:
                    row = dict(source_row)
                    if table == "ctl_connection":
                        original = row["fabric_connection_id"]
                        if original not in config["connections"]:
                            raise RuntimeError(f"Missing {environment} control connector mapping: {original}")
                        row["fabric_connection_id"] = config["connections"][original]
                        row["environment_name"] = environment
                        row["connection_name"] = f"{environment}_{row['connection_name']}"
                    if table in ("ctl_source_object", "ctl_transform_object"):
                        row["is_active"] = False
                    if identity == "schema_contract_key":
                        row.pop(identity)
                        where = "source_object_id=? AND contract_version=?"
                        key_values = (row["source_object_id"], row["contract_version"])
                    else:
                        where, key_values = f"{quote(identity)}=?", (row[identity],)
                    columns = list(row)
                    sql = f"INSERT INTO control.{quote(table)} ({','.join(map(quote, columns))},dwh_created_ts" + (",dwh_updated_ts" if table != "ctl_schema_contract" else "") + ") SELECT "
                    sql += ",".join("?" for _ in columns) + ",SYSUTCDATETIME()" + (",SYSUTCDATETIME()" if table != "ctl_schema_contract" else "")
                    sql += f" WHERE NOT EXISTS (SELECT 1 FROM control.{quote(table)} WHERE {where})"
                    connection.execute(sql, *row.values(), *key_values)
            # Empty baseline state, never copied from Production and never reset on rerun.
            connection.execute("""INSERT INTO control.ctl_load_state
              (source_object_id,load_status,initial_load_completed,last_successful_watermark,dwh_updated_ts)
              SELECT source_object_id,'ready',0,'1900-01-01T00:00:00.000',SYSUTCDATETIME()
              FROM control.ctl_source_object s WHERE NOT EXISTS
              (SELECT 1 FROM control.ctl_load_state t WHERE t.source_object_id=s.source_object_id)""")
            connection.execute("""INSERT INTO control.ctl_transform_state
              (transform_object_id,transform_status,baseline_completed,last_processed_bronze_batch_key,dwh_updated_ts)
              SELECT transform_object_id,'ready',0,0,SYSUTCDATETIME()
              FROM control.ctl_transform_object s WHERE NOT EXISTS
              (SELECT 1 FROM control.ctl_transform_state t WHERE t.transform_object_id=s.transform_object_id)""")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    print(json.dumps({"environment": environment, "status": "metadata_seeded", "source_and_transform_objects": "disabled_pending_integration"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--environment", choices=["dev", "test"])
    args = parser.parse_args()
    if args.export:
        export_metadata()
    elif args.environment:
        bootstrap(args.environment)
    else:
        parser.error("Choose --export or --environment")


if __name__ == "__main__":
    main()
