"""Validate local Markdown links without cloud access or external URL probing."""

import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]


def check():
    files = [ROOT / "README.md", ROOT / "SECURITY.md", *(ROOT / "docs").rglob("*.md")]
    errors = []
    for source in files:
        for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", source.read_text()):
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            path = source.parent / unquote(target.split("#", 1)[0])
            if not path.exists():
                errors.append(f"{source.relative_to(ROOT)}: missing {target}")
    if errors:
        raise RuntimeError("\n".join(errors))
    print({"markdown_files": len(files), "local_links": "passed"})


if __name__ == "__main__":
    check()
