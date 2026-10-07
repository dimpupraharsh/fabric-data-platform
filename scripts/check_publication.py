"""Check publishable paths without printing secret values or contacting a cloud.

Inputs: a Git checkout containing the reviewed source and docs.
Output: file count on success; path/rule/line diagnostics on failure.
This is a conservative local/CI guard, not a comprehensive secret-detection tool.
"""

import ast
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "aws-access-key": re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "github-token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "private-key": re.compile(r"^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.M),
    "embedded-postgres-password": re.compile(r"postgres(?:ql)?://[^\s/:]+:([^\s@]+)@", re.I),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),
    "credential-literal": re.compile(
        r"\b(?:password|pwd|client_secret|aws_secret_access_key)\b\s*[:=]\s*['\"]?([^\s'\";,}\n]{8,})", re.I
    ),
}
BLOCKED_PARTS = {"datasets", "extracts", "generated_events", ".terraform", "output", "__pycache__"}
BLOCKED_SUFFIXES = {".csv", ".parquet", ".docx", ".pdf", ".pem", ".pfx", ".key", ".tfplan"}


def publishable_paths(root=ROOT):
    """Include tracked and non-ignored candidate files, excluding Git internals."""
    output = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root
    ).decode()
    return sorted({Path(path) for path in output.split("\0") if path})


def check(root=ROOT):
    """Reject unsafe paths/obvious tokens and syntax-check publishable Python."""
    issues = []
    paths = publishable_paths(root)
    for relative in paths:
        path = root / relative
        if not path.is_file():
            continue
        if (BLOCKED_PARTS.intersection(relative.parts) or relative.suffix in BLOCKED_SUFFIXES
                or relative.name.startswith("secrets") or ".tfstate" in relative.name
                or (relative.name.startswith(".env") and relative.name != ".env.example")):
            issues.append(f"{relative}: forbidden publication path")
            continue
        if path.stat().st_size > 5_000_000:
            issues.append(f"{relative}: oversized artifact; review before publication")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            if relative.suffix not in {".png", ".jpg", ".jpeg"}:
                issues.append(f"{relative}: unreviewed binary")
            continue
        for rule, pattern in RULES.items():
            for match in pattern.finditer(content):
                if rule == "embedded-postgres-password" and (
                        "${" in match.group(1) or "<" in match.group(1)):
                    continue
                if rule == "credential-literal" and (
                        "${" in match.group(1) or "<" in match.group(1)):
                    continue
                line = content.count("\n", 0, match.start()) + 1
                issues.append(f"{relative}:{line}: {rule}")
        if relative.suffix == ".py":
            ast.parse(content, filename=str(relative))
    if issues:
        raise RuntimeError("Publication check failed:\n" + "\n".join(issues))
    return {"files_checked": len(paths), "status": "passed"}


if __name__ == "__main__":
    print(check())
