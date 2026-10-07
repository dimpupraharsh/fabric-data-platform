import argparse
from pathlib import Path

import psycopg


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a PostgreSQL SQL file against a database.")
    parser.add_argument("--dsn", required=True, help="PostgreSQL connection string.")
    parser.add_argument("sql_file", help="Path to the SQL file to execute.")
    args = parser.parse_args()

    sql_path = Path(args.sql_file).expanduser().resolve()
    sql_text = sql_path.read_text(encoding="utf-8")

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)

    print(f"Executed {sql_path}")


if __name__ == "__main__":
    main()
