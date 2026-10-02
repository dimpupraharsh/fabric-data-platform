"""Fail closed on query API errors without calling Fabric or Power BI."""

from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy"))
from test_semantic_acceptance import query_totals


def test_semantic_errors_fail_even_with_http_200():
    for payload in ({"error": {"code": "Denied"}}, {"results": [{"error": {"code": "QueryFailed"}}]},
                    {"results": [{"tables": [{"rows": [{"[Sales]": 230}]}]}]}):
        with pytest.raises(RuntimeError):
            query_totals(payload)


def test_semantic_fixture_totals_are_exact():
    values = {"[Sales]": 230, "[Lines]": 4, "[Orders]": 4, "[SLA]": 2}
    result = query_totals({"results": [{"tables": [{"rows": [values]}]}]})
    assert result == {"Sales": Decimal(230), "Lines": Decimal(4), "Orders": Decimal(4), "SLA": Decimal(2)}


def test_semantic_plan_is_nonmutating():
    result = subprocess.run([sys.executable, str(ROOT / "deploy/test_semantic_acceptance.py"),
                             "--environment", "test"], check=True, capture_output=True, text=True)
    plan = json.loads(result.stdout)
    assert plan["mode"] == "plan" and plan["production_changes"] == 0
