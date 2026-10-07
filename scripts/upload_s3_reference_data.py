import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path


APPROVED_UPLOADS = {
    "location_master": {
        "local_path": Path("location_master/location_master.csv"),
        "s3_key": "retail_ref/location_master/location_master.csv",
        "prefix": "retail_ref/location_master/",
    },
    "delivery_zone_lookup": {
        "local_path": Path("delivery_zone_lookup/delivery_zone_lookup.csv"),
        "s3_key": "retail_ref/delivery_zone_lookup/delivery_zone_lookup.csv",
        "prefix": "retail_ref/delivery_zone_lookup/",
    },
    "warehouse_coverage": {
        "local_path": Path("warehouse_coverage/warehouse_coverage.csv"),
        "s3_key": "retail_ref/warehouse_coverage/warehouse_coverage.csv",
        "prefix": "retail_ref/warehouse_coverage/",
    },
    "geo_hierarchy": {
        "local_path": Path("geo_hierarchy/geo_hierarchy.csv"),
        "s3_key": "retail_ref/geo_hierarchy/geo_hierarchy.csv",
        "prefix": "retail_ref/geo_hierarchy/",
    },
}


def count_csv_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        return max(sum(1 for _ in csv.reader(handle)) - 1, 0)


def validate_upload_plan(base_path: Path) -> list[dict[str, object]]:
    plan = []
    for dataset_name, config in APPROVED_UPLOADS.items():
        local_path = (base_path / config["local_path"]).resolve()
        s3_key = config["s3_key"]
        prefix = config["prefix"]

        if not s3_key.startswith(prefix):
            raise ValueError(f"Upload key for {dataset_name} is outside approved prefix: {s3_key}")
        if not local_path.exists():
            raise FileNotFoundError(f"Missing local source file for {dataset_name}: {local_path}")

        plan.append(
            {
                "dataset_name": dataset_name,
                "local_path": local_path,
                "s3_key": s3_key,
                "row_count": count_csv_rows(local_path),
            }
        )
    return plan


def get_s3_client(region: str):
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError as exc:  # pragma: no cover - dependency guard for CLI users
        raise SystemExit("boto3 is required. Install dependencies with: .venv/bin/python -m pip install -r requirements.txt") from exc

    # Use the SDK credential chain: profiles, SSO, roles or environment variables.
    return boto3.client("s3", region_name=region), ClientError


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload approved S3 reference CSV files.")
    parser.add_argument("--bucket", required=True, help="Existing private S3 bucket name.")
    parser.add_argument("--base-path", default="datasets/s3_reference", help="Local generated reference root.")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "eu-north-1"), help="AWS region.")
    parser.add_argument("--dry-run", action="store_true", help="Print upload plan without writing to S3.")
    args = parser.parse_args()

    base_path = Path(args.base_path).expanduser().resolve()
    plan = validate_upload_plan(base_path)

    print("Upload plan:")
    for item in plan:
        print(f"- {item['dataset_name']}: {item['row_count']:,} rows -> s3://{args.bucket}/{item['s3_key']}")

    if args.dry_run:
        return

    s3, client_error = get_s3_client(args.region)
    try:
        s3.head_bucket(Bucket=args.bucket)
    except client_error as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code not in {"403", "Forbidden"}:
            raise
        print("Bucket metadata check returned 403; continuing with object-level uploads to approved keys only.")

    uploaded = []
    for item in plan:
        s3.upload_file(
            Filename=str(item["local_path"]),
            Bucket=args.bucket,
            Key=item["s3_key"],
            ExtraArgs={
                "ContentType": "text/csv",
                "ServerSideEncryption": "AES256",
                "Metadata": {
                    "source_role": "retail_reference_enrichment",
                    "dataset_name": str(item["dataset_name"]),
                    "generated_by": "fabric_retail_pre_bronze_source_setup",
                },
            },
        )
        try:
            head = s3.head_object(Bucket=args.bucket, Key=item["s3_key"])
            size_bytes = head["ContentLength"]
            last_modified = head["LastModified"].isoformat()
            verification_status = "head_object_verified"
        except client_error as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code not in {"403", "Forbidden"}:
                raise
            size_bytes = item["local_path"].stat().st_size
            last_modified = None
            verification_status = "put_object_succeeded_head_object_forbidden"
        uploaded.append(
            {
                "dataset_name": item["dataset_name"],
                "s3_uri": f"s3://{args.bucket}/{item['s3_key']}",
                "row_count": item["row_count"],
                "size_bytes": size_bytes,
                "last_modified": last_modified,
                "verification_status": verification_status,
            }
        )
        print(f"Uploaded s3://{args.bucket}/{item['s3_key']} ({verification_status})")

    manifest = {
        "uploaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "bucket": args.bucket,
        "region": args.region,
        "allowed_prefixes": [config["prefix"] for config in APPROVED_UPLOADS.values()],
        "objects": uploaded,
    }
    manifest_path = base_path / "s3_upload_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Upload manifest written to {manifest_path}")


if __name__ == "__main__":
    main()
