"""Exercise deployed control procedures using a dedicated non-production fixture.

This tests metadata contracts, not Copy/Spark or physical manifests. The fixture
never reads source rows or writes Lakehouse/Gold data. Its audit records remain
for diagnosis; its source object is disabled on exit. Production is prohibited.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import pyodbc

from export_sql_schema import connect, quote
from fabric_api import FabricAPI

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ID = 900001
FIXTURE_NAME = "__cicd_control_contract_fixture"


def result(connection, statement, *parameters):
    """Consume procedure result sets so deferred SQL errors cannot be ignored."""
    cursor = connection.execute(statement, *parameters)
    output = None
    while True:
        if cursor.description:
            names = [column[0] for column in cursor.description]
            rows = [dict(zip(names, row)) for row in cursor.fetchall()]
            if rows:
                output = rows[0]
        if not cursor.nextset():
            return output


def expect_error(connection, message, statement, *parameters):
    """A negative test passes only when the intended guard raises its error."""
    try:
        result(connection, statement, *parameters)
    except pyodbc.Error as error:
        if message not in str(error):
            raise
        return
    raise AssertionError(f"Expected SQL guard did not fire: {message}")


def run_contracts(connection):
    """Verify checkpoint safety, lease exclusion, retry, replay and drift guards."""
    existing = connection.execute(
        "SELECT source_object_name FROM control.ctl_source_object WHERE source_object_id=?", FIXTURE_ID).fetchall()
    if existing and (len(existing) != 1 or existing[0][0] != FIXTURE_NAME):
        raise RuntimeError("Reserved CI fixture ID is already owned by another object")
    if not existing:
        columns = [row[0] for row in connection.execute("""SELECT name FROM sys.columns
          WHERE object_id=OBJECT_ID('control.ctl_source_object') AND is_identity=0 ORDER BY column_id""").fetchall()]
        # Clone shape only; every locator/path is visibly a test-only sentinel.
        overrides = {"source_object_id": FIXTURE_ID, "source_object_name": FIXTURE_NAME,
                     "source_locator": FIXTURE_NAME, "source_table_name": FIXTURE_NAME,
                     "bronze_target_name": FIXTURE_NAME, "load_group": "cicd_contract",
                     "landing_relative_path": "Files/cicd_validation/control_contract",
                     "manifest_relative_path": "Files/cicd_validation/control_contract",
                     "is_active": 0}
        expressions = ["?" if name in overrides else quote(name) for name in columns]
        values = [overrides[name] for name in columns if name in overrides]
        connection.execute("INSERT INTO control.ctl_source_object (" + ",".join(map(quote, columns)) +
                           ") SELECT " + ",".join(expressions) +
                           " FROM control.ctl_source_object WHERE source_object_id=1003", *values)
        connection.execute("""INSERT INTO control.ctl_schema_contract
          (source_object_id,contract_version,contract_status,drift_action,expected_columns_csv,
           expected_schema_hash,effective_from_ts,dwh_created_ts,expected_schema_json,approved_by)
          SELECT ?,contract_version,contract_status,drift_action,expected_columns_csv,
            expected_schema_hash,SYSUTCDATETIME(),SYSUTCDATETIME(),expected_schema_json,'cicd_contract_fixture'
          FROM control.ctl_schema_contract WHERE source_object_id=1003
            AND contract_status='approved' AND effective_to_ts IS NULL""", FIXTURE_ID)
        connection.execute("""INSERT INTO control.ctl_load_state
          (source_object_id,load_status,initial_load_completed,last_successful_watermark,
           last_successful_tie_breaker,dwh_updated_ts)
          VALUES (?,'ready',0,CAST('1900-01-01' AS DATETIME2(3)),'0',SYSUTCDATETIME())""", FIXTURE_ID)
    state = connection.execute("""SELECT last_successful_watermark,lock_owner_run_id
      FROM control.ctl_load_state WHERE source_object_id=?""", FIXTURE_ID).fetchall()
    if len(state) != 1 or state[0][1] is not None:
        raise RuntimeError("Fixture checkpoint is missing, duplicated, or leased by another test")
    previous = state[0][0]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    upper = max(now, previous + timedelta(seconds=1))
    upper = upper.replace(microsecond=(upper.microsecond // 1000) * 1000)
    contract = connection.execute("""SELECT expected_columns_csv FROM control.ctl_schema_contract
      WHERE source_object_id=? AND contract_status='approved' AND effective_to_ts IS NULL""", FIXTURE_ID).fetchall()
    if len(contract) != 1:
        raise RuntimeError("Fixture must have exactly one current approved schema contract")
    columns = contract[0][0]
    prefix = "ci-contract-" + uuid4().hex
    owned_runs = []
    prepare_sql = """EXEC control.sp_prepare_bronze_watermark_run @pipeline_run_id=?,
      @source_object_id=?,@upper_watermark=?,@upper_tie_breaker='1',
      @observed_columns_csv=?,@observed_schema_json=?"""

    def prepare(suffix, timestamp=upper, observed=columns):
        run_id = prefix + suffix
        owned_runs.append(run_id)
        return run_id, result(connection, prepare_sql, run_id, FIXTURE_ID, timestamp,
                              observed, '{"fixture":true,"scope":"control_contract_only"}')

    def checkpoint():
        return connection.execute("SELECT last_successful_watermark FROM control.ctl_load_state WHERE source_object_id=?",
                                  FIXTURE_ID).fetchone()[0]

    connection.execute("UPDATE control.ctl_source_object SET is_active=1 WHERE source_object_id=?", FIXTURE_ID)
    try:
        owner, staged = prepare("-stage")
        assert staged["can_write"] and checkpoint() == previous
        batch = staged["ingestion_batch_id"]
        _, competing = prepare("-compete")
        assert not competing["can_write"] and competing["batch_action"] == "lock_not_acquired"
        result(connection, """EXEC control.sp_set_bronze_expected_rows @pipeline_run_id=?,
          @source_object_id=?,@ingestion_batch_id=?,@rows_expected=1""", owner, FIXTURE_ID, batch)
        commit_sql = """EXEC control.sp_commit_bronze_watermark_run @pipeline_run_id=?,
          @source_object_id=?,@ingestion_batch_id=?,@rows_landed=?,@manifest_written=?"""
        expect_error(connection, "Commit blocked:", commit_sql, owner, FIXTURE_ID, batch, 2, 1)
        expect_error(connection, "Commit blocked:", commit_sql, owner, FIXTURE_ID, batch, 1, 0)
        assert checkpoint() == previous
        result(connection, """EXEC control.sp_fail_bronze_watermark_run @pipeline_run_id=?,
          @source_object_id=?,@ingestion_batch_id=?,@error_category='cicd_expected_failure',
          @error_message='Test-only failure; no physical data was copied.'""", owner, FIXTURE_ID, batch)
        assert checkpoint() == previous
        retry, resumed = prepare("-retry")
        assert resumed["can_write"] and resumed["ingestion_batch_id"] == batch
        # The manifest flag here is fixture metadata, not a claim of a physical file.
        committed = result(connection, commit_sql, retry, FIXTURE_ID, batch, 1, 1)
        assert committed["committed_now"] and checkpoint() == upper
        _, replay = prepare("-replay")
        assert not replay["can_write"] and replay["batch_action"] == "no_change"
        count = connection.execute("SELECT COUNT(*) FROM control.ctl_bronze_batch WHERE source_object_id=? AND ingestion_batch_id=?",
                                   FIXTURE_ID, batch).fetchone()[0]
        assert count == 1
        drift_run = prefix + "-drift"
        owned_runs.append(drift_run)
        expect_error(connection, "Breaking source schema drift blocked before Copy", prepare_sql,
                     drift_run, FIXTURE_ID, upper + timedelta(seconds=1), columns + ",unexpected_column",
                     '{"fixture":true,"scope":"control_contract_only"}')
        assert checkpoint() == upper
        drift_count = connection.execute("SELECT COUNT(*) FROM control.ctl_schema_drift_event WHERE pipeline_run_id=?",
                                         drift_run).fetchone()[0]
        assert drift_count == 1
        return {"status": "passed", "scope": "control_contract_only", "fixture_source_object_id": FIXTURE_ID,
                "checks": ["no_premature_checkpoint", "lease_exclusion", "count_guard", "manifest_guard",
                           "failed_run_checkpoint_safety", "resume_same_batch", "commit", "replay", "drift_block"]}
    finally:
        # Never clear another test's lease or any actual source object's state.
        for run_id in owned_runs:
            connection.execute("""UPDATE control.ctl_load_state SET load_status='ready',lock_owner_run_id=NULL,
              lock_acquired_ts=NULL,lock_expires_ts=NULL WHERE source_object_id=? AND lock_owner_run_id=?""",
                               FIXTURE_ID, run_id)
        connection.execute("UPDATE control.ctl_source_object SET is_active=0 WHERE source_object_id=?", FIXTURE_ID)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["dev", "test"], required=True)
    args = parser.parse_args()
    config = json.loads((ROOT / "config/environments.json").read_text())[args.environment]
    api = FabricAPI()
    warehouse = next(item for item in api.list_all(f"workspaces/{config['workspace_id']}/items")
                     if item["type"] == "Warehouse" and item["displayName"] == "wh_retail_control")
    with connect(api, config["workspace_id"], warehouse["id"]) as connection:
        report = run_contracts(connection)
    print(json.dumps({"environment": args.environment, **report}))


if __name__ == "__main__":
    main()
