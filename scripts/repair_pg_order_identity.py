#!/usr/bin/env python3
"""Align legacy synthetic order lines/events with the source order header.

The update is resumable: a rerun skips lines already equal to their header.
Each committed batch receives a new source watermark for Fabric replay.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

import psycopg


def repair_sales(conn: psycopg.Connection, batch_size: int) -> int:
    """Repair one sales_key range at a time; return the changed line count."""
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(sales_key), 0) FROM retail_oi.sales_order_line")
        max_key = cur.fetchone()[0]

    changed = 0
    for lower in range(0, max_key, batch_size):
        upper = lower + batch_size
        watermark = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE retail_oi.sales_order_line AS s
                SET customer_id = h.customer_id,
                    order_date = h.order_date,
                    ship_date = h.ship_date,
                    due_date = h.due_date,
                    dwh_load_ts = %s
                FROM retail_oi.order_header AS h
                WHERE s.sales_key > %s AND s.sales_key <= %s
                  AND s.order_number = h.order_number
                  AND (s.order_number LIKE 'SIM%%' OR s.order_number LIKE 'PG%%')
                  AND (s.customer_id, s.order_date, s.ship_date, s.due_date)
                      IS DISTINCT FROM
                      (h.customer_id, h.order_date, h.ship_date, h.due_date)
                """,
                (watermark, lower, upper),
            )
            batch_changed = cur.rowcount
        conn.commit()
        changed += batch_changed
        print(f"sales_key ({lower}, {upper}]: repaired {batch_changed:,}; total {changed:,}", flush=True)
    return changed


def repair_event_times(conn: psycopg.Connection) -> dict[str, int]:
    """Move legacy SIM event times onto their order's UTC business timeline."""
    statuses = {
        "order_status_event": ("event_status", {"created": 0, "packed": 1, "shipped": 2,
                                                "delivered": 4, "cancelled": 0, "returned": 7}),
        "shipment_status_event": ("shipment_status", {"pending": 0, "in_transit": 2,
                                                       "delayed": 5, "delivered": 4}),
        "payment_status_event": ("payment_status", {"pending": 0, "paid": 0,
                                                     "failed": 0, "refunded": 7}),
    }
    counts: dict[str, int] = {}
    for table, (column, offset_days) in statuses.items():
        cases = " ".join(f"WHEN '{status}' THEN {days}" for status, days in offset_days.items())
        watermark = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE retail_oi.{table} AS e
                SET event_ts = (h.order_date::timestamp AT TIME ZONE 'UTC')
                               + (CASE e.{column} {cases} ELSE 0 END) * INTERVAL '1 day'
                               + (e.event_key %% 1440) * INTERVAL '1 minute',
                    dwh_load_ts = %s
                FROM retail_oi.order_header AS h
                WHERE e.order_number = h.order_number
                  AND e.order_number LIKE 'SIM%%'
                  AND e.event_ts::date > h.order_date + INTERVAL '30 days'
                """,
                (watermark,),
            )
            counts[table] = cur.rowcount
        conn.commit()
        print(f"{table}: repaired {counts[table]:,} event timestamps", flush=True)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--batch-size", type=int, default=500_000)
    parser.add_argument("--sales-only", action="store_true")
    args = parser.parse_args()
    if args.batch_size <= 0:
        raise ValueError("batch-size must be positive")

    with psycopg.connect(args.dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('retail_oi.order_header')")
            if cur.fetchone()[0] is None:
                raise RuntimeError("Run postgres/05_create_order_header.pg.sql first")
        repaired_sales = repair_sales(conn, args.batch_size)
        repaired_events = {} if args.sales_only else repair_event_times(conn)
        with conn.cursor() as cur:
            for table in ["sales_order_line", *repaired_events]:
                cur.execute(f"ANALYZE retail_oi.{table}")
        conn.commit()
    print({"repaired_sales_lines": repaired_sales, "repaired_event_rows": repaired_events})


if __name__ == "__main__":
    main()
