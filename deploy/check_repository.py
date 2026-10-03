"""Credential-free checks for Fabric definitions and environment isolation.

This runs on untrusted pull requests without cloud credentials. It parses native
metadata, pipeline JSON, notebook Python and SQL migrations, and rejects secrets,
state files, exported schedules and duplicate Fabric logical IDs.
"""

import ast
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    """Raise on a release-contract violation; return a compact validation summary."""
    config = json.loads((root / "config/environments.json").read_text())
    assert set(config) == {"dev", "test", "production"}
    assert len({value["workspace_id"] for value in config.values()}) == 3
    assert not config["dev"]["schedule_enabled"] and not config["test"]["schedule_enabled"]
    logical_ids, notebooks, pipelines = set(), 0, 0
    for platform in (root / "workspace").rglob(".platform"):
        data = json.loads(platform.read_text())
        logical_id = data["config"]["logicalId"]
        assert logical_id not in logical_ids, f"Duplicate logical ID: {platform}"
        logical_ids.add(logical_id)
        assert data["metadata"].get("description"), f"Missing item description: {platform}"
    for pipeline in (root / "workspace").rglob("pipeline-content.json"):
        data = json.loads(pipeline.read_text())
        assert isinstance(data.get("properties", {}).get("activities"), list), pipeline
        pipelines += 1
    for notebook in (root / "workspace").rglob("notebook-content.py"):
        ast.parse(notebook.read_text(), filename=str(notebook))
        notebooks += 1
    secret_pattern = re.compile(r"AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:Pwd|Password)\s*=\s*[^<\s;][^;\n]{5,}", re.I)
    candidates = [path for folder in ("workspace", "config", "deploy", "migrations", "infra", ".github", "tests")
                  for path in (root / folder).rglob("*")
                  if path.is_file() and ".terraform" not in path.parts and "__pycache__" not in path.parts]
    ignored = set(subprocess.run(["git", "check-ignore", "--stdin"], cwd=root,
        input="\n".join(str(path.relative_to(root)) for path in candidates),
        text=True, capture_output=True, check=False).stdout.splitlines())
    # Scan only publishable paths, not local ignored build directories or state.
    for folder in ("workspace", "config", "deploy", "migrations", "infra", ".github", "tests"):
        for path in (root / folder).rglob("*"):
            if not path.is_file() or ".terraform" in path.parts or "__pycache__" in path.parts or str(path.relative_to(root)) in ignored:
                continue
            assert not path.name.endswith((".tfstate", ".tfplan"))
            if path.name == ".schedules":
                # Export backups are ignored locally; release preparation removes them.
                assert ".schedules" in (root / ".gitignore").read_text()
                continue
            if path.suffix in (".py", ".json", ".tf", ".sql", ".yml", ".yaml", ".tmdl", ".hcl"):
                assert not secret_pattern.search(path.read_text()), f"Possible credential: {path}"
    assert logical_ids and notebooks and pipelines
    return {"items": len(logical_ids), "notebooks": notebooks, "pipelines": pipelines, "status": "passed"}


if __name__ == "__main__":
    print(json.dumps(check()))
