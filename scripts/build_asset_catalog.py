"""Generate a navigable catalogue from native Fabric definitions, not live APIs.

Input: workspace/.platform, pipeline JSON and native notebook Python.
Output: docs/asset-catalog.md, including pipeline parameters/variables/activities.
No identity, source data, Fabric API or secret file is read.
"""

import json
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/asset-catalog.md"


def cell(value):
    """Keep multi-line descriptions and pipes inside a single Markdown cell."""
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def activities(value, scope=""):
    """Traverse nested Switch/ForEach/If branches without flattening their scope."""
    if isinstance(value, dict):
        if "name" in value and "type" in value and "typeProperties" in value:
            name = f"{scope}/{value['name']}" if scope else value["name"]
            yield name, value
            scope = name
        for child in value.values():
            yield from activities(child, scope)
    elif isinstance(value, list):
        for child in value:
            yield from activities(child, scope)


def build():
    """Read local definitions deterministically and write the documentation source."""
    lines = ["# Fabric Asset Catalogue", "",
             "Generated from repository definitions, not a live workspace inventory.",
             "Regenerate with `python scripts/build_asset_catalog.py` after item changes.",
             "Environment binding and release gates still apply; this is not a deployment instruction.", "",
             "## Items", "", "| Item | Type | Description |", "| --- | --- | --- |"]
    platforms = sorted((ROOT / "workspace").glob("*/.platform"))
    for platform in platforms:
        metadata = json.loads(platform.read_text())["metadata"]
        target = quote("../" + str(platform.parent.relative_to(ROOT)), safe="/.")
        lines.append(f"| [{cell(metadata.get('displayName', platform.parent.name))}]({target}) "
                     f"| {cell(metadata.get('type'))} | {cell(metadata.get('description'))} |")
    count = 0
    for pipeline in sorted((ROOT / "workspace").glob("*.DataPipeline/pipeline-content.json")):
        name = pipeline.parent.name.removesuffix(".DataPipeline")
        props = json.loads(pipeline.read_text())["properties"]
        lines += ["", f"## {name}", "", f"Concurrency: `{props.get('concurrency', 'not explicitly set')}`.", ""]
        for label, key in (("Parameters", "parameters"), ("Variables", "variables")):
            lines += [f"### {label}", ""]
            definitions = props.get(key, {})
            if not definitions:
                lines += ["None declared.", ""]
            else:
                lines += ["| Name | Type | Default |", "| --- | --- | --- |"]
                for parameter, definition in sorted(definitions.items()):
                    lines.append(f"| {cell(parameter)} | {cell(definition.get('type'))} "
                                 f"| {cell(definition.get('defaultValue', 'not supplied'))} |")
                lines.append("")
        lines += ["### Activities", "", "| Activity path | Type | Description |", "| --- | --- | --- |"]
        for path, activity in activities(props.get("activities", [])):
            count += 1
            lines.append(f"| {cell(path)} | {cell(activity['type'])} "
                         f"| {cell(activity.get('description', 'No description in saved definition'))} |")
    DEST.write_text("\n".join(lines) + "\n")
    return {"items": len(platforms), "activities": count, "output": str(DEST.relative_to(ROOT))}


if __name__ == "__main__":
    print(build())
