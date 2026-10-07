#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
dsn="${POSTGRES_DSN:?Set POSTGRES_DSN for a disposable PostgreSQL source}"
if [[ "${ALLOW_SOURCE_REBUILD:-}" != "yes" ]]; then
  printf '%s\n' 'Refusing destructive rebuild. Back up the source, then set ALLOW_SOURCE_REBUILD=yes.' >&2
  exit 1
fi

"$project_root/.venv/bin/python" "$project_root/scripts/run_postgres_sql_file.py" \
  --dsn "$dsn" "$project_root/postgres/01_create_retail_oi_tables.pg.sql"
"$project_root/.venv/bin/python" "$project_root/scripts/load_csv_to_postgres_staging.py" \
  --dsn "$dsn" --base-path "$project_root/datasets" --truncate
"$project_root/.venv/bin/python" "$project_root/scripts/run_postgres_sql_file.py" \
  --dsn "$dsn" "$project_root/postgres/02_seed_retail_oi_from_staging.pg.sql"
"$project_root/.venv/bin/python" "$project_root/scripts/run_postgres_sql_file.py" \
  --dsn "$dsn" "$project_root/postgres/03_extend_customer_master_for_s3_alignment.pg.sql"
"$project_root/.venv/bin/python" "$project_root/scripts/align_postgres_customer_geo_to_s3.py" \
  --dsn "$dsn" --location-master-path "$project_root/datasets/s3_reference/location_master/location_master.csv"
"$project_root/.venv/bin/python" "$project_root/scripts/run_postgres_sql_file.py" \
  --dsn "$dsn" "$project_root/postgres/04_deduplicate_customer_master.pg.sql"
"$project_root/.venv/bin/python" "$project_root/scripts/scale_postgres_sales_fact.py" \
  --dsn "$dsn" --target-sales-rows 15000000 --batch-size 500000

"$project_root/.venv/bin/python" "$project_root/scripts/run_postgres_sql_file.py" \
  --dsn "$dsn" "$project_root/postgres/05_create_order_header.pg.sql"
"$project_root/.venv/bin/python" "$project_root/scripts/repair_pg_order_identity.py" \
  --dsn "$dsn" --batch-size 500000
"$project_root/.venv/bin/python" "$project_root/scripts/run_postgres_sql_file.py" \
  --dsn "$dsn" "$project_root/postgres/06_extend_order_header_status.pg.sql"
