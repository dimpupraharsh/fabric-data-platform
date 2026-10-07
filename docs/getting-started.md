# Safe Setup and Source Simulation

## Read Before Running

This repository contains code, not source data or cloud account access.
CRM/ERP seed CSVs are not redistributed. You supply licensed/private inputs
and your own connections. Validation is safe; source rebuilds, simulations,
S3 uploads and cloud releases are write operations requiring explicit intent.

## Local Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-source.txt
python scripts/check_publication.py
python deploy/check_repository.py
pytest -q
```

Python 3.12 is the CI target. PostgreSQL uses Docker/OrbStack and psycopg.
Fabric Spark supplies PySpark/Delta; local tests are not a Spark execution proof.
Warehouse connections require ODBC Driver 18 and appropriate identity access.

## Credentials and Networking

Use `.env.example` as a template for local values; never commit populated files.
Docker Compose reads `.env`; Python scripts read exported environment variables
or CLI arguments, not `.env` automatically. Set `POSTGRES_DSN` privately.
AWS scripts use the standard SDK profile/SSO/role/environment credential chain.
Do not paste credentials into issues, shell history or documentation.

Compose binds PostgreSQL to loopback by default. For a Windows gateway VM,
explicitly set `POSTGRES_BIND_ADDRESS` to the reachable private Mac interface
and restrict firewall/authentication. A successful TCP test does not prove
Fabric connection authentication or Copy works.

```bash
docker compose -f docker-compose.postgres.yml up -d
```

## Owned PostgreSQL Source

Place these private inputs beneath `datasets/`:

- `cust_info.csv`, `CUST_AZ12.csv`, `LOC_A101.csv`
- `prd_info.csv`, `PX_CAT_G1V2.csv`, `sales_details.csv`
- The generated/downloaded S3 location snapshot under `datasets/s3_reference/`.

`postgres/01_create_retail_oi_tables.pg.sql` drops/recreates project tables.
`rebuild_postgres_source.sh` therefore refuses execution unless
`ALLOW_SOURCE_REBUILD=yes`. Back up first; use a disposable database. A rebuild
changes the source baseline and is not compatible with blindly reusing an old
Fabric watermark. Never execute it against an application production source.

| Tool | Purpose |
| --- | --- |
| `run_postgres_sql_file.py` | Execute a chosen PostgreSQL SQL file using an explicit DSN |
| `load_csv_to_postgres_staging.py` | Load CSVs to staging; `--truncate` is destructive |
| `align_postgres_customer_geo_to_s3.py` | Owned-source customer geography alignment |
| `scale_postgres_sales_fact.py` | Batched sales scaling, default target 15M lines |
| `repair_pg_order_identity.py` | Explicit source identity repair, not routine ingestion |
| `simulate_pg_incremental_changes.py` | New/updated sales, events, late dates and controlled defects |
| `validate_pg_incremental_changes.py` | Changed-row, reference and dirty-data diagnostics |

After a valid source baseline, explicitly generate a small change batch:

```bash
python scripts/simulate_pg_incremental_changes.py \
  --inserted-sales-count 1200 --updated-sales-count 250 \
  --event-count 500 --dirty-data-rate 0.005
python scripts/validate_pg_incremental_changes.py \
  --previous-watermark YOUR_LAST_COMMITTED_UTC_TIMESTAMP
```

The DSN comes from `POSTGRES_DSN`. Inserts can include controlled duplicates;
actual committed counts come from the run log, not assumptions about arguments.
Use the Fabric committed boundary for validation, not a stale source-side
simulation watermark. Source tools must not advance Fabric checkpoints.

## S3 Reference Files

Generate project geography/fulfilment data locally first. Postal identifiers
are project-generated join keys, not an authoritative global postal registry.

```bash
python scripts/generate_s3_reference_data.py \
  --postal-codes-per-city 500 --as-of-date 2026-10-07
python scripts/upload_s3_reference_data.py \
  --bucket "$S3_REFERENCE_BUCKET" --dry-run
```

The upload script writes only the four configured `retail_ref` keys. Remove
`--dry-run` only with an authorized private bucket and intended upload.
For slow-changing reference refresh, run the refresh tool locally; `--upload`
explicitly replaces complete S3 files:

```bash
python scripts/simulate_s3_reference_refresh.py \
  --change-count 40 --run-date 2026-10-07
```

Generated data/manifests remain ignored. Cloud-side encryption/ACL defaults do
not replace bucket-policy and public-access-block verification.

## Fabric Deployment

Do not run every bootstrap/reference SQL file in numerical order against an
existing Warehouse. Some files retire legacy models or initialize state.
Use [the release runbook](release-runbook.md) and versioned migrations.
Environment IDs in this portfolio are original project bindings; do not reuse
them for another tenant. Provision/rebind connectors and Warehouse schemas
separately. CI validates definitions; it does not grant cloud access.
