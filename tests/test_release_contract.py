"""Offline checks for migration parsing and fail-closed release configuration."""

import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy"))
from check_repository import check
from migrate import batches
from release import prepare


def test_repository_contract():
    assert check()["items"] == 24


def test_go_is_standalone():
    assert batches("SELECT 'GO';\nGO\nSELECT 2;\nGO -- separator") == ["SELECT 'GO';", "SELECT 2;"]


def test_production_disabled_until_gates_pass():
    with pytest.raises(RuntimeError, match="disabled"):
        prepare("production", "application")


def test_foundation_has_no_schedules():
    _, directory, _ = prepare("test", "foundation")
    assert not list(directory.rglob(".schedules"))


def test_environment_isolation():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "config/environments.json").read_text())
    assert len({item["workspace_id"] for item in config.values()}) == 3
    for source in ("ffb74af9-9d17-4429-8493-02465e631244",
                   "0a85b5ac-b0d0-4686-9de2-c3bf62dac800",
                   "aedad88b-3c1c-470e-8f95-bfafb37f40c5"):
        assert len({item["connections"][source] for item in config.values()}) == 3


def test_control_contract_runner_forbids_production():
    import subprocess
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / "deploy/test_control_contracts.py"),
                             "--environment", "production"], capture_output=True, text=True)
    assert result.returncode != 0 and "invalid choice" in result.stderr
