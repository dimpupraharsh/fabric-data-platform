"""Apply checksum-locked, additive Warehouse migrations to a selected environment.

Input: environment and checked-in VNNN__*.sql files. Output: applied/skipped
versions. No Production checkpoint or data bootstrap is performed. Each version
and its ledger entry commit together; changed historical migrations fail closed.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

from export_sql_schema import connect
from fabric_api import FabricAPI

ROOT = Path(__file__).resolve().parents[1]


def batches(sql):
    """Split standalone GO lines, not occurrences inside SQL expressions."""
    return [part.strip() for part in re.split(r"(?im)^\s*GO\s*(?:--[^\n]*)?$", sql) if part.strip()]


def migrate(connection, directory):
    """Apply a version exactly once; reject a checksum change on later runs."""
    connection.execute("IF SCHEMA_ID('deployment') IS NULL EXEC('CREATE SCHEMA deployment')")
    connection.execute("""IF OBJECT_ID('deployment.schema_version','U') IS NULL
      CREATE TABLE deployment.schema_version (
        version_name varchar(200) NOT NULL, sha256 varchar(64) NOT NULL,
        applied_ts datetime2(3) NOT NULL, commit_sha varchar(64) NULL)""")
    results = []
    for path in sorted(directory.glob("V*__*.sql")):
        sql = path.read_text()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        previous = connection.execute(
            "SELECT sha256 FROM deployment.schema_version WHERE version_name=?", path.name).fetchall()
        if previous:
            if len(previous) != 1 or previous[0][0] != digest:
                raise RuntimeError(f"Migration ledger mismatch: {path.name}")
            results.append({"version": path.name, "status": "already_applied"})
            continue
        # Fabric transactions protect both additive DDL and migration bookkeeping.
        connection.autocommit = False
        try:
            for statement in batches(sql):
                connection.execute(statement)
            import os
            connection.execute("""INSERT INTO deployment.schema_version
              (version_name,sha256,applied_ts,commit_sha) VALUES (?,?,SYSUTCDATETIME(),?)""",
              path.name, digest, os.environ.get("GITHUB_SHA"))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.autocommit = True
        results.append({"version": path.name, "status": "applied"})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["dev", "test", "production"], required=True)
    args = parser.parse_args()
    config = json.loads((ROOT / "config/environments.json").read_text())[args.environment]
    if not config["sql_migrations_enabled"]:
        raise RuntimeError("SQL migrations are not enabled for this environment")
    api = FabricAPI()
    items = api.list_all(f"workspaces/{config['workspace_id']}/items")
    for name in ("wh_retail_control", "wh_retail_gold"):
        item = next(x for x in items if x["type"] == "Warehouse" and x["displayName"] == name)
        with connect(api, config["workspace_id"], item["id"]) as connection:
            print(json.dumps({"warehouse": name, "migrations": migrate(connection, ROOT / "migrations" / name)}))


if __name__ == "__main__":
    main()
