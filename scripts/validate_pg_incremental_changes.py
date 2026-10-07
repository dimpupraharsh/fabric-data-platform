import argparse
import os
from datetime import datetime, timezone

import psycopg


REQUIRED_TABLES = {
    "retail_oi.customer_master",
    "retail_oi.product_master",
    "retail_oi.sales_order_line",
    "retail_oi.order_status_event",
    "retail_oi.shipment_status_event",
    "retail_oi.payment_status_event",
    "retail_oi.watermark_control",
    "retail_oi.source_simulation_run",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PostgreSQL incremental source changes.")
    parser.add_argument("--dsn", default=os.environ.get("POSTGRES_DSN"),
                        required=not bool(os.environ.get("POSTGRES_DSN")),
                        help="PostgreSQL DSN; defaults to POSTGRES_DSN.")
    parser.add_argument("--previous-watermark", help="Override previous watermark timestamp in ISO-8601 format.")
    return parser.parse_args()


def scalar(cur: psycopg.Cursor, sql: str, params: tuple | None = None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def ensure_required_tables(cur: psycopg.Cursor) -> None:
    cur.execute(
        """
        SELECT table_schema || '.' || table_name
        FROM information_schema.tables
        WHERE (table_schema || '.' || table_name) = ANY(%s)
        """,
        (sorted(REQUIRED_TABLES),),
    )
    found = {row[0] for row in cur.fetchall()}
    missing = sorted(REQUIRED_TABLES - found)
    if missing:
        raise RuntimeError(f"Missing required PostgreSQL tables: {', '.join(missing)}")


def parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def available_run_log_columns(cur: psycopg.Cursor) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'retail_oi'
          AND table_name = 'source_simulation_run'
        """
    )
    return {row[0] for row in cur.fetchall()}


def get_watermark(cur: psycopg.Cursor, source_table: str, override: str | None) -> datetime:
    if override:
        return parse_utc_timestamp(override)
    cur.execute(
        """
        SELECT last_watermark_val
        FROM retail_oi.watermark_control
        WHERE source_table = %s
        """,
        (source_table,),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"Missing watermark_control row for {source_table}")
    return row[0]


def latest_run(cur: psycopg.Cursor) -> dict | None:
    available = available_run_log_columns(cur)
    select_map = {
        "simulation_run_key": "simulation_run_key",
        "run_id": "run_id",
        "run_started_ts": "run_started_ts",
        "run_completed_ts": "run_completed_ts",
        "inserted_sales_rows": "inserted_sales_rows",
        "updated_sales_rows": "updated_sales_rows",
        "inserted_order_events": "inserted_order_events",
        "inserted_shipment_events": "inserted_shipment_events",
        "inserted_payment_events": "inserted_payment_events",
        "dirty_rows_injected": "dirty_rows_injected",
        "status": "status",
    }
    select_list = []
    for alias, column_name in select_map.items():
        if column_name in available:
            select_list.append(column_name)
        else:
            select_list.append(f"NULL AS {alias}")
    order_by_started = "COALESCE(run_started_ts, started_at)" if "run_started_ts" in available else "started_at"

    cur.execute(
        f"""
        SELECT {", ".join(select_list)}
        FROM retail_oi.source_simulation_run
        ORDER BY {order_by_started} DESC, simulation_run_key DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "simulation_run_key": row[0],
        "run_id": row[1],
        "run_started_ts": row[2],
        "run_completed_ts": row[3],
        "inserted_sales_rows": row[4],
        "updated_sales_rows": row[5],
        "inserted_order_events": row[6],
        "inserted_shipment_events": row[7],
        "inserted_payment_events": row[8],
        "dirty_rows_injected": row[9],
        "status": row[10],
    }


def report_table_change(cur: psycopg.Cursor, table_name: str, watermark: datetime) -> tuple[int, datetime | None, datetime | None]:
    cur.execute(
        f"""
        SELECT COUNT(*), MIN(dwh_load_ts), MAX(dwh_load_ts)
        FROM {table_name}
        WHERE dwh_load_ts > %s
        """,
        (watermark,),
    )
    row = cur.fetchone()
    return row[0], row[1], row[2]


def report_run_window_count(
    cur: psycopg.Cursor,
    table_name: str,
    run_started_ts: datetime | None,
    run_completed_ts: datetime | None,
) -> int | None:
    if run_started_ts is None or run_completed_ts is None:
        return None
    cur.execute(
        f"""
        SELECT COUNT(*)
        FROM {table_name}
        WHERE dwh_load_ts BETWEEN %s AND %s
        """,
        (run_started_ts, run_completed_ts),
    )
    row = cur.fetchone()
    return row[0] if row else 0


def main() -> None:
    args = parse_args()

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            ensure_required_tables(cur)
            run = latest_run(cur)

            sales_watermark = get_watermark(cur, "sales_order_line", args.previous_watermark)
            order_watermark = get_watermark(cur, "order_status_event", args.previous_watermark)
            shipment_watermark = get_watermark(cur, "shipment_status_event", args.previous_watermark)
            payment_watermark = get_watermark(cur, "payment_status_event", args.previous_watermark)

            sales_changed, sales_min_ts, sales_max_ts = report_table_change(cur, "retail_oi.sales_order_line", sales_watermark)
            order_changed, order_min_ts, order_max_ts = report_table_change(cur, "retail_oi.order_status_event", order_watermark)
            shipment_changed, shipment_min_ts, shipment_max_ts = report_table_change(cur, "retail_oi.shipment_status_event", shipment_watermark)
            payment_changed, payment_min_ts, payment_max_ts = report_table_change(cur, "retail_oi.payment_status_event", payment_watermark)
            run_window_sales = report_run_window_count(
                cur,
                "retail_oi.sales_order_line",
                run["run_started_ts"] if run else None,
                run["run_completed_ts"] if run else None,
            )
            run_window_orders = report_run_window_count(
                cur,
                "retail_oi.order_status_event",
                run["run_started_ts"] if run else None,
                run["run_completed_ts"] if run else None,
            )
            run_window_shipments = report_run_window_count(
                cur,
                "retail_oi.shipment_status_event",
                run["run_started_ts"] if run else None,
                run["run_completed_ts"] if run else None,
            )
            run_window_payments = report_run_window_count(
                cur,
                "retail_oi.payment_status_event",
                run["run_started_ts"] if run else None,
                run["run_completed_ts"] if run else None,
            )

            missing_customer_refs = scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM retail_oi.sales_order_line sol
                LEFT JOIN retail_oi.customer_master cm
                  ON cm.customer_id = sol.customer_id
                WHERE sol.dwh_load_ts > %s
                  AND cm.customer_id IS NULL
                """,
                (sales_watermark,),
            )
            missing_product_refs = scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM retail_oi.sales_order_line sol
                LEFT JOIN retail_oi.product_master pm
                  ON pm.product_business_key = sol.product_business_key
                WHERE sol.dwh_load_ts > %s
                  AND pm.product_business_key IS NULL
                """,
                (sales_watermark,),
            )
            dirty_ship = scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM retail_oi.sales_order_line
                WHERE dwh_load_ts > %s
                  AND ship_date IS NOT NULL
                  AND ship_date < order_date
                """,
                (sales_watermark,),
            )
            dirty_due = scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM retail_oi.sales_order_line
                WHERE dwh_load_ts > %s
                  AND due_date IS NOT NULL
                  AND due_date < order_date
                """,
                (sales_watermark,),
            )
            dirty_sales = scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM retail_oi.sales_order_line
                WHERE dwh_load_ts > %s
                  AND ROUND(sales_amount::numeric, 2) <> ROUND((quantity * unit_price)::numeric, 2)
                """,
                (sales_watermark,),
            )
            duplicate_groups = scalar(
                cur,
                """
                WITH changed AS (
                    SELECT order_number, product_business_key, customer_id, order_date, quantity, unit_price, sales_amount
                    FROM retail_oi.sales_order_line
                    WHERE dwh_load_ts > %s
                )
                SELECT COUNT(*)
                FROM (
                    SELECT order_number, product_business_key, customer_id, order_date, quantity, unit_price, sales_amount
                    FROM changed
                    GROUP BY order_number, product_business_key, customer_id, order_date, quantity, unit_price, sales_amount
                    HAVING COUNT(*) > 1
                ) d
                """,
                (sales_watermark,),
            )
            dirty_total = dirty_ship + dirty_due + dirty_sales + duplicate_groups
            dirty_threshold = max(5, int(max(sales_changed, 1) * 0.02))
            dirty_within_control = dirty_total <= dirty_threshold

    print("PG_INCREMENTAL_VALIDATION")
    print(f"previous_sales_watermark\t{sales_watermark}")
    print(f"previous_sales_watermark_is_baseline\t{str(sales_watermark.year == 1900).lower()}")
    print(f"previous_order_event_watermark\t{order_watermark}")
    print(f"previous_shipment_event_watermark\t{shipment_watermark}")
    print(f"previous_payment_event_watermark\t{payment_watermark}")
    if run:
        print(f"latest_run_id\t{run['run_id']}")
        print(f"latest_run_status\t{run['status']}")
        print(f"latest_run_started_ts\t{run['run_started_ts']}")
        print(f"latest_run_completed_ts\t{run['run_completed_ts']}")
        print(f"logged_inserted_sales_rows\t{run['inserted_sales_rows']}")
        print(f"logged_updated_sales_rows\t{run['updated_sales_rows']}")
        print(f"logged_inserted_order_events\t{run['inserted_order_events']}")
        print(f"logged_inserted_shipment_events\t{run['inserted_shipment_events']}")
        print(f"logged_inserted_payment_events\t{run['inserted_payment_events']}")
        print(f"logged_dirty_rows_injected\t{run['dirty_rows_injected']}")
        print(f"run_window_sales_rows\t{run_window_sales}")
        print(f"run_window_order_event_rows\t{run_window_orders}")
        print(f"run_window_shipment_event_rows\t{run_window_shipments}")
        print(f"run_window_payment_event_rows\t{run_window_payments}")
    print(f"changed_sales_rows\t{sales_changed}")
    print(f"changed_sales_min_dwh_load_ts\t{sales_min_ts}")
    print(f"changed_sales_max_dwh_load_ts\t{sales_max_ts}")
    print(f"changed_order_event_rows\t{order_changed}")
    print(f"changed_order_event_min_dwh_load_ts\t{order_min_ts}")
    print(f"changed_order_event_max_dwh_load_ts\t{order_max_ts}")
    print(f"changed_shipment_event_rows\t{shipment_changed}")
    print(f"changed_shipment_event_min_dwh_load_ts\t{shipment_min_ts}")
    print(f"changed_shipment_event_max_dwh_load_ts\t{shipment_max_ts}")
    print(f"changed_payment_event_rows\t{payment_changed}")
    print(f"changed_payment_event_min_dwh_load_ts\t{payment_min_ts}")
    print(f"changed_payment_event_max_dwh_load_ts\t{payment_max_ts}")
    print(f"missing_customer_references\t{missing_customer_refs}")
    print(f"missing_product_references\t{missing_product_refs}")
    print(f"dirty_ship_date_before_order_date\t{dirty_ship}")
    print(f"dirty_due_date_before_order_date\t{dirty_due}")
    print(f"dirty_sales_amount_mismatch\t{dirty_sales}")
    print(f"dirty_duplicate_business_line_groups\t{duplicate_groups}")
    print(f"dirty_rows_total\t{dirty_total}")
    print(f"dirty_control_threshold\t{dirty_threshold}")
    print(f"dirty_rows_within_control_threshold\t{str(dirty_within_control).lower()}")

    run_succeeded = run is None or run["status"] in (None, "succeeded", "running")
    ready = missing_customer_refs == 0 and missing_product_refs == 0 and dirty_within_control and run_succeeded
    print(f"latest_run_succeeded_or_not_present\t{str(run_succeeded).lower()}")
    print(f"ready_for_incremental_bronze_run\t{str(ready).lower()}")


if __name__ == "__main__":
    main()
