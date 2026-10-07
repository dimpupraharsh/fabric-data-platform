import argparse
import csv
from pathlib import Path

import psycopg


TABLE_FILES = {
    "cust_info.csv": "retail_oi.stg_cust_info",
    "CUST_AZ12.csv": "retail_oi.stg_cust_az12",
    "LOC_A101.csv": "retail_oi.stg_loc_a101",
    "prd_info.csv": "retail_oi.stg_prd_info",
    "PX_CAT_G1V2.csv": "retail_oi.stg_px_cat_g1v2",
    "sales_details.csv": "retail_oi.stg_sales_details",
}


def find_csv(base_path: Path, filename: str) -> Path:
    direct_path = base_path / filename
    if direct_path.exists():
        return direct_path

    matches = sorted(base_path.rglob(filename))
    if not matches:
        raise FileNotFoundError(f"Expected CSV file is missing under {base_path}: {filename}")
    if len(matches) > 1:
        match_list = ", ".join(str(match) for match in matches)
        raise RuntimeError(f"Found multiple matches for {filename}: {match_list}")

    return matches[0]


def count_rows(csv_path: Path) -> int:
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        return max(sum(1 for _ in csv.reader(handle)) - 1, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load seed CSV files into PostgreSQL staging tables.")
    parser.add_argument("--dsn", required=True, help="PostgreSQL connection string.")
    parser.add_argument("--base-path", required=True, help="Directory containing the seed CSV files.")
    parser.add_argument("--truncate", action="store_true", help="Truncate staging tables before loading.")
    args = parser.parse_args()

    base_path = Path(args.base_path).expanduser().resolve()
    if not base_path.exists():
        raise FileNotFoundError(f"CSV base path does not exist: {base_path}")

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            if args.truncate:
                for table_name in TABLE_FILES.values():
                    print(f"Truncating {table_name}")
                    cur.execute(f"TRUNCATE TABLE {table_name}")

            for filename, table_name in TABLE_FILES.items():
                csv_path = find_csv(base_path, filename)
                print(f"Loading {csv_path} -> {table_name}")
                with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    with cur.copy(f"COPY {table_name} FROM STDIN WITH (FORMAT csv, HEADER true)") as copy:
                        while chunk := handle.read(65536):
                            copy.write(chunk)
                print(f"Loaded {count_rows(csv_path):,} rows into {table_name}")


if __name__ == "__main__":
    main()
