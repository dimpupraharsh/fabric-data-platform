"""Offline fixture safety tests; cloud results are a separate requirement."""

import ast
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy"))
from test_business_acceptance import EXPECTED_CHECKS, require_business_evidence


def test_empty_success_is_not_business_acceptance():
    with pytest.raises(RuntimeError, match="twelve"):
        require_business_evidence({"status": "Succeeded", "output": {"result": {"exitValue": None}}})


def test_business_evidence_requires_all_checks_and_isolation():
    evidence = {"status": "passed", "checks": sorted(EXPECTED_CHECKS),
                "source_mutations": 0, "ingestion_checkpoint_updates": 0}
    activity = {"output": {"result": {"exitValue": json.dumps(evidence)}}}
    assert require_business_evidence(activity) == evidence
    evidence["ingestion_checkpoint_updates"] = 1
    activity["output"]["result"]["exitValue"] = json.dumps(evidence)
    with pytest.raises(RuntimeError, match="isolated"):
        require_business_evidence(activity)


def test_acceptance_plan_is_nonmutating():
    result = subprocess.run([sys.executable, str(ROOT / "deploy/test_business_acceptance.py"),
                             "--environment", "test"], capture_output=True, text=True, check=True)
    plan = json.loads(result.stdout)
    assert plan["mode"] == "plan" and len(plan["assets"]) == 5
    assert plan["source_changes"] == plan["production_changes"] == plan["checkpoint_changes"] == 0


def test_acceptance_prohibits_production():
    result = subprocess.run([sys.executable, str(ROOT / "deploy/test_business_acceptance.py"),
                             "--environment", "production", "--execute"], capture_output=True, text=True)
    assert result.returncode != 0 and "invalid choice" in result.stderr


def test_fixture_compiles_without_local_spark():
    tree = ast.parse((ROOT / "deploy/business_fixture.py").read_text())
    compile(tree, "business_fixture.py", "exec")


def test_business_gate_is_test_only_and_preserves_evidence():
    import yaml
    workflow = yaml.safe_load((ROOT / ".github/workflows/release-environment.yml").read_text())
    steps = workflow["jobs"]["release"]["steps"]
    gate = next(step for step in steps if "test_business_acceptance.py" in step.get("run", ""))
    assert gate["if"] == "inputs.environment == 'test'"
    evidence = next(step for step in steps if step.get("name") == "Preserve business acceptance evidence")
    assert evidence["if"] == "always() && inputs.environment == 'test'"
    assert evidence["with"]["path"] == "output/business_acceptance.json"


def test_transformation_exit_contract():
    for name in ("dimensions", "sales", "events", "order_header"):
        source = (ROOT / f"workspace/nb_silver_{name}.Notebook/notebook-content.py").read_text()
        body = ast.parse(source.split("# CELL ********************", 1)[1])
        exits = [node for node in body.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                 and ast.unparse(node.value.func) == "notebookutils.notebook.exit"]
        assert len(exits) == 1
