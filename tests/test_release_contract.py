"""Offline checks for migration parsing and fail-closed release configuration."""

import sys
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
