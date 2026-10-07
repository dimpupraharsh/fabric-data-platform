"""Ensure cleanup cannot turn an upstream failed activity into child success."""

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def groups(activities):
    """Walk activity scopes without incorrectly crossing container boundaries."""
    yield activities
    for activity in activities:
        properties = activity.get("typeProperties", {})
        for key in ("activities", "ifTrueActivities", "ifFalseActivities", "defaultActivities"):
            yield from groups(properties.get(key, []))
        for case in properties.get("cases", []):
            yield from groups(case.get("activities", []))


def test_cleanup_branches_preserve_pipeline_failure():
    count = 0
    for name in ("pl_bronze_pg_watermark", "pl_silver_orchestrator"):
        definition = json.loads((ROOT / f"workspace/{name}.DataPipeline/pipeline-content.json").read_text())
        for activities in groups(definition["properties"]["activities"]):
            for activity in activities:
                if activity["type"] != "Script" or not any(
                        "Failed" in dependency["dependencyConditions"]
                        for dependency in activity.get("dependsOn", [])):
                    continue
                downstream = [candidate for candidate in activities if candidate["type"] == "Fail"
                              and candidate.get("dependsOn") == [{"activity": activity["name"],
                                                                   "dependencyConditions": ["Completed"]}]]
                assert len(downstream) == 1, activity["name"]
                assert downstream[0]["description"]
                assert downstream[0]["typeProperties"]["errorCode"] == "RETAIL_UPSTREAM_ACTIVITY_FAILED"
                count += 1
    assert count == 11


def test_fault_injection_plan_is_nonmutating_and_test_only():
    script = ROOT / "deploy/test_failure_paths.py"
    result = subprocess.run([sys.executable, str(script), "--environment", "test"],
                            check=True, capture_output=True, text=True)
    plan = json.loads(result.stdout)
    assert plan["mode"] == "plan" and plan["source_changes"] == plan["checkpoint_changes"] == 0
    denied = subprocess.run([sys.executable, str(script), "--environment", "production", "--execute"],
                            capture_output=True, text=True)
    assert denied.returncode != 0 and "invalid choice" in denied.stderr
