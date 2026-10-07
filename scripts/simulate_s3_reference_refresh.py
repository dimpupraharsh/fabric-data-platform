import argparse
import csv
import hashlib
import json
import os
import random
from datetime import date, datetime, timezone
from pathlib import Path


try:
    import boto3
except ImportError:  # pragma: no cover - optional upload dependency
    boto3 = None


APPROVED_OBJECTS = {
    "location_master": "retail_ref/location_master/location_master.csv",
    "delivery_zone_lookup": "retail_ref/delivery_zone_lookup/delivery_zone_lookup.csv",
    "warehouse_coverage": "retail_ref/warehouse_coverage/warehouse_coverage.csv",
    "geo_hierarchy": "retail_ref/geo_hierarchy/geo_hierarchy.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate a slow-changing S3 reference refresh.")
    parser.add_argument("--base-path", default="datasets/s3_reference")
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--change-count", type=int, default=40)
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--bucket", default="fabric-datawarehouse-project")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "eu-north-1"))
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def stable_suffix(seed: str, width: int = 3) -> str:
    digest = hashlib.md5(seed.encode("utf-8"), usedforsecurity=False).hexdigest()
    return digest[:width].upper()


def next_postal_code(postal_code: str, counter: int) -> str:
    suffix = stable_suffix(f"{postal_code}-{counter}", width=3)
    if postal_code.startswith(("US-", "FR-", "DE-", "CA-")):
        return postal_code[:-3] + suffix
    if postal_code.startswith(("GB-", "AU-")):
        return postal_code + suffix
    return f"{postal_code}-{suffix}"


def upload_file(s3, bucket: str, key: str, path: Path) -> dict:
    s3.upload_file(
        Filename=str(path),
        Bucket=bucket,
        Key=key,
        ExtraArgs={
            "ContentType": "text/csv",
            "ServerSideEncryption": "AES256",
            "Metadata": {"source_role": "retail_reference_refresh"},
        },
    )
    head = s3.head_object(Bucket=bucket, Key=key)
    return {
        "s3_uri": f"s3://{bucket}/{key}",
        "size_bytes": head["ContentLength"],
        "uploaded_at": head["LastModified"].isoformat(),
    }


def get_s3_client(region: str):
    if boto3 is None:
        raise RuntimeError("boto3 is required for --upload")
    # Do not collect or embed keys; let the standard AWS SDK chain authenticate.
    return boto3.client("s3", region_name=region)


def main() -> None:
    args = parse_args()
    if args.change_count <= 0:
        raise ValueError("--change-count must be greater than zero")

    run_date = date.fromisoformat(args.run_date)
    rng = random.Random(run_date.isoformat())
    base = Path(args.base_path).expanduser().resolve()

    files = {
        "location_master": base / "location_master/location_master.csv",
        "delivery_zone_lookup": base / "delivery_zone_lookup/delivery_zone_lookup.csv",
        "warehouse_coverage": base / "warehouse_coverage/warehouse_coverage.csv",
        "geo_hierarchy": base / "geo_hierarchy/geo_hierarchy.csv",
    }

    location_rows = read_csv(files["location_master"])
    delivery_rows = read_csv(files["delivery_zone_lookup"])
    warehouse_rows = read_csv(files["warehouse_coverage"])
    geo_rows = read_csv(files["geo_hierarchy"])
    if not location_rows or not delivery_rows or not warehouse_rows or not geo_rows:
        raise RuntimeError("All four reference CSV files must exist and contain rows before refresh simulation can run")

    location_by_postal = {row["postal_code"]: row for row in location_rows}
    delivery_by_postal = {row["postal_code"]: row for row in delivery_rows}
    warehouse_rows_by_postal: dict[str, list[dict[str, str]]] = {}
    for row in warehouse_rows:
        warehouse_rows_by_postal.setdefault(row["covered_postal_code"], []).append(row)

    change_summary = {
        "sla_updates": 0,
        "serviceability_flips": 0,
        "inactive_location_updates": 0,
        "new_postal_codes": 0,
        "warehouse_sla_updates": 0,
    }

    candidate_postals = sorted(location_by_postal)
    rng.shuffle(candidate_postals)

    for postal_code in candidate_postals[: args.change_count]:
        delivery = delivery_by_postal[postal_code]
        delivery["last_updated_date"] = run_date.isoformat()
        if change_summary["sla_updates"] < max(1, args.change_count // 3):
            delivery["standard_sla_days"] = str(max(1, int(delivery["standard_sla_days"]) + rng.choice([-1, 1])))
            delivery["express_sla_days"] = str(max(1, int(delivery["express_sla_days"]) + rng.choice([-1, 0, 1])))
            change_summary["sla_updates"] += 1
        if change_summary["serviceability_flips"] < max(1, args.change_count // 4):
            delivery["serviceability_flag"] = "False" if delivery["serviceability_flag"] == "True" else "True"
            change_summary["serviceability_flips"] += 1

        for wh_row in warehouse_rows_by_postal.get(postal_code, []):
            wh_row["last_updated_date"] = run_date.isoformat()
            wh_row["max_sla_days"] = str(max(1, int(wh_row["max_sla_days"]) + rng.choice([-1, 0, 1])))
            change_summary["warehouse_sla_updates"] += 1

    for location in candidate_postals[: max(1, args.change_count // 5)]:
        row = location_by_postal[location]
        row["is_active"] = "False"
        row["effective_to"] = run_date.isoformat()
        change_summary["inactive_location_updates"] += 1

    new_source_postals = candidate_postals[: max(2, args.change_count // 10)]
    for counter, source_postal in enumerate(new_source_postals, start=1):
        src_location = dict(location_by_postal[source_postal])
        new_postal = next_postal_code(source_postal, counter)
        if new_postal in location_by_postal:
            continue
        src_location["location_id"] = f"{src_location['location_id']}_R{counter:03d}"
        src_location["postal_code"] = new_postal
        src_location["effective_from"] = run_date.isoformat()
        src_location["effective_to"] = ""
        src_location["is_active"] = "True"
        location_rows.append(src_location)
        location_by_postal[new_postal] = src_location

        src_delivery = dict(delivery_by_postal[source_postal])
        src_delivery["postal_code"] = new_postal
        src_delivery["last_updated_date"] = run_date.isoformat()
        delivery_rows.append(src_delivery)
        delivery_by_postal[new_postal] = src_delivery

        for wh_row in warehouse_rows_by_postal.get(source_postal, []):
            cloned = dict(wh_row)
            cloned["covered_postal_code"] = new_postal
            cloned["last_updated_date"] = run_date.isoformat()
            warehouse_rows.append(cloned)
            warehouse_rows_by_postal.setdefault(new_postal, []).append(cloned)

        change_summary["new_postal_codes"] += 1

    for row in geo_rows:
        row["last_updated_date"] = run_date.isoformat()

    write_csv(files["location_master"], location_rows)
    write_csv(files["delivery_zone_lookup"], delivery_rows)
    write_csv(files["warehouse_coverage"], warehouse_rows)
    write_csv(files["geo_hierarchy"], geo_rows)

    manifest = {
        "run_date": run_date.isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": {
            name: {
                "row_count": len(read_csv(path)),
                "path": str(path),
                "object_key": APPROVED_OBJECTS[name],
                "upload_timestamp": None,
            }
            for name, path in files.items()
        },
        "change_summary": change_summary,
    }

    if args.upload:
        s3 = get_s3_client(args.region)
        uploaded = {}
        for name, path in files.items():
            uploaded[name] = upload_file(s3, args.bucket, APPROVED_OBJECTS[name], path)
            manifest["files"][name]["upload_timestamp"] = uploaded[name]["uploaded_at"]
        manifest["uploaded"] = uploaded

    manifest_path = base / "s3_refresh_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("S3 reference refresh simulation complete.")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
