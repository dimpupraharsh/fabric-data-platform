import argparse
from datetime import date

import psycopg


def scalar(cur: psycopg.Cursor, sql: str, params: dict | None = None) -> int:
    cur.execute(sql, params or {})
    row = cur.fetchone()
    return row[0] if row else 0


def ensure_seed_state(cur: psycopg.Cursor) -> tuple[int, int, int]:
    customer_count = scalar(cur, "SELECT COUNT(*) FROM retail_oi.customer_master;")
    product_count = scalar(cur, "SELECT COUNT(*) FROM retail_oi.product_master;")
    current_rows = scalar(cur, "SELECT COUNT(*) FROM retail_oi.sales_order_line;")

    if customer_count == 0:
        raise RuntimeError("customer_master must be loaded before scaling")
    if product_count == 0:
        raise RuntimeError("product_master must be loaded before scaling")

    return customer_count, product_count, current_rows


def build_temp_maps(cur: psycopg.Cursor) -> None:
    cur.execute("DROP TABLE IF EXISTS pg_temp.tmp_customers;")
    cur.execute("DROP TABLE IF EXISTS pg_temp.tmp_products;")

    cur.execute(
        """
        CREATE TEMP TABLE tmp_customers ON COMMIT PRESERVE ROWS AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY customer_id, customer_key)::INT AS rn,
            customer_id
        FROM retail_oi.customer_master;
        """
    )
    cur.execute("CREATE UNIQUE INDEX tmp_customers_rn_idx ON tmp_customers (rn);")

    cur.execute(
        """
        CREATE TEMP TABLE tmp_products ON COMMIT PRESERVE ROWS AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY product_business_key, product_key)::INT AS rn,
            product_business_key,
            COALESCE(NULLIF(product_cost, 0), (10 + (ROW_NUMBER() OVER (ORDER BY product_business_key, product_key) % 300))::NUMERIC(18,2))::NUMERIC(18,2) AS base_price
        FROM retail_oi.product_master;
        """
    )
    cur.execute("CREATE UNIQUE INDEX tmp_products_rn_idx ON tmp_products (rn);")


def insert_sales_batch(
    cur: psycopg.Cursor,
    *,
    rows_to_insert: int,
    batch_start: int,
    avg_lines_per_order: int,
    customer_count: int,
    product_count: int,
    start_date: date,
    date_span: int,
) -> None:
    cur.execute(
        """
        WITH n AS (
            SELECT generate_series(1, %(rows_to_insert)s) AS rn
        ),
        shaped AS (
            SELECT
                rn,
                %(batch_start)s::BIGINT + rn - 1 AS global_line_number,
                ((%(batch_start)s::BIGINT + rn - 2) / %(avg_lines_per_order)s) + 1 AS generated_order_number,
                (((((%(batch_start)s::BIGINT + rn - 2) / %(avg_lines_per_order)s) + 1) * 101 - 1) %% %(customer_count)s + 1)::INT AS customer_rn,
                (((%(batch_start)s::BIGINT + rn * 202 - 1) %% %(product_count)s) + 1)::INT AS product_rn,
                (((%(batch_start)s::BIGINT + rn - 2) / %(avg_lines_per_order)s) + 1) * 303 AS date_seed,
                (%(batch_start)s::BIGINT + rn * 404) AS qty_seed,
                (%(batch_start)s::BIGINT + rn * 505) AS price_seed
            FROM n
        ),
        priced AS (
            SELECT
                s.rn,
                s.generated_order_number,
                'SIM' || LPAD(s.generated_order_number::TEXT, 12, '0') AS order_number,
                p.product_business_key,
                c.customer_id,
                (%(start_date)s::DATE + ((s.date_seed %% %(date_span)s)::INT)) AS order_date,
                1 + ((s.qty_seed %% 5)::INT) AS quantity,
                ROUND((p.base_price * (1.10 + ((s.price_seed %% 35)::NUMERIC / 100.0)))::NUMERIC, 2) AS unit_price
            FROM shaped AS s
            JOIN tmp_customers AS c
              ON c.rn = s.customer_rn
            JOIN tmp_products AS p
              ON p.rn = s.product_rn
        ),
        final_rows AS (
            SELECT
                rn,
                generated_order_number,
                order_number,
                product_business_key,
                customer_id,
                order_date,
                order_date + (1 + (generated_order_number %% 5))::INT AS ship_date,
                order_date + (3 + (generated_order_number %% 8))::INT AS due_date,
                quantity,
                unit_price,
                ROUND((quantity * unit_price)::NUMERIC, 2) AS sales_amount
            FROM priced
        )
        INSERT INTO retail_oi.sales_order_line (
            order_number,
            product_business_key,
            customer_id,
            order_date,
            ship_date,
            due_date,
            sales_amount,
            quantity,
            unit_price,
            dwh_load_ts,
            dwh_source_system
        )
        SELECT
            order_number,
            product_business_key,
            customer_id,
            order_date,
            ship_date,
            due_date,
            sales_amount,
            quantity,
            unit_price,
            NOW(),
            'sim'
        FROM final_rows;
        """,
        {
            "rows_to_insert": rows_to_insert,
            "batch_start": batch_start,
            "avg_lines_per_order": avg_lines_per_order,
            "customer_count": customer_count,
            "product_count": product_count,
            "start_date": start_date.isoformat(),
            "date_span": date_span,
        },
    )


def insert_event_batch(
    cur: psycopg.Cursor,
    *,
    table_name: str,
    status_column: str,
    case_sql: str,
    event_ts_offset_sql: str,
    rows_to_insert: int,
    batch_start: int,
    avg_lines_per_order: int,
    start_date: date,
    date_span: int,
    event_sample_percent: int,
) -> None:
    cur.execute(
        f"""
        WITH n AS (
            SELECT generate_series(1, %(rows_to_insert)s) AS rn
        ),
        event_orders AS (
            SELECT
                'SIM' || LPAD(((((%(batch_start)s::BIGINT + rn - 2) / %(avg_lines_per_order)s) + 1))::TEXT, 12, '0') AS order_number,
                ((%(start_date)s::DATE + (((((%(batch_start)s::BIGINT + rn - 2) / %(avg_lines_per_order)s) + 1) * 303) %% %(date_span)s)::INT)::TIMESTAMP AT TIME ZONE 'UTC')
                    + ((rn %% 1440)::INT * INTERVAL '1 minute') AS event_ts,
                rn
            FROM n
            WHERE rn %% 100 < %(event_sample_percent)s
        )
        INSERT INTO retail_oi.{table_name} (
            order_number,
            {status_column},
            event_ts,
            dwh_load_ts,
            dwh_source_system
        )
        SELECT
            order_number,
            {case_sql},
            {event_ts_offset_sql},
            NOW(),
            'sim'
        FROM event_orders;
        """,
        {
            "rows_to_insert": rows_to_insert,
            "batch_start": batch_start,
            "avg_lines_per_order": avg_lines_per_order,
            "start_date": start_date.isoformat(),
            "date_span": date_span,
            "event_sample_percent": event_sample_percent,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Scale local PostgreSQL sales_order_line to Azure-like volume.")
    parser.add_argument("--dsn", required=True, help="PostgreSQL connection string.")
    parser.add_argument("--target-sales-rows", type=int, default=15_000_000)
    parser.add_argument("--batch-size", type=int, default=500_000)
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--avg-lines-per-order", type=int, default=3)
    parser.add_argument("--event-sample-percent", type=int, default=5)
    parser.add_argument("--skip-events", action="store_true")
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    if start_date > end_date:
        raise ValueError("start-date must be less than or equal to end-date")
    if args.target_sales_rows <= 0:
        raise ValueError("target-sales-rows must be greater than zero")
    if args.batch_size <= 0:
        raise ValueError("batch-size must be greater than zero")
    if args.avg_lines_per_order <= 0:
        raise ValueError("avg-lines-per-order must be greater than zero")
    if not 0 <= args.event_sample_percent <= 100:
        raise ValueError("event-sample-percent must be between 0 and 100")

    with psycopg.connect(args.dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            customer_count, product_count, current_rows = ensure_seed_state(cur)
            if current_rows >= args.target_sales_rows:
                print(
                    f"sales_order_line already has {current_rows:,} rows, "
                    f"which is >= target {args.target_sales_rows:,}. Nothing to do."
                )
                return

            build_temp_maps(cur)
            conn.commit()

            date_span = (end_date - start_date).days + 1
            inserted_total = 0

            while current_rows < args.target_sales_rows:
                rows_to_insert = min(args.batch_size, args.target_sales_rows - current_rows)
                batch_start = current_rows + 1

                insert_sales_batch(
                    cur,
                    rows_to_insert=rows_to_insert,
                    batch_start=batch_start,
                    avg_lines_per_order=args.avg_lines_per_order,
                    customer_count=customer_count,
                    product_count=product_count,
                    start_date=start_date,
                    date_span=date_span,
                )

                if not args.skip_events and args.event_sample_percent > 0:
                    insert_event_batch(
                        cur,
                        table_name="order_status_event",
                        status_column="event_status",
                        case_sql="""
                            CASE rn %% 5
                                WHEN 0 THEN 'created'
                                WHEN 1 THEN 'packed'
                                WHEN 2 THEN 'shipped'
                                WHEN 3 THEN 'delivered'
                                ELSE 'cancelled'
                            END
                        """,
                        event_ts_offset_sql="event_ts",
                        rows_to_insert=rows_to_insert,
                        batch_start=batch_start,
                        avg_lines_per_order=args.avg_lines_per_order,
                        start_date=start_date,
                        date_span=date_span,
                        event_sample_percent=args.event_sample_percent,
                    )
                    insert_event_batch(
                        cur,
                        table_name="shipment_status_event",
                        status_column="shipment_status",
                        case_sql="""
                            CASE rn %% 3
                                WHEN 0 THEN 'in_transit'
                                WHEN 1 THEN 'delivered'
                                ELSE 'delayed'
                            END
                        """,
                        event_ts_offset_sql="event_ts + INTERVAL '12 hours'",
                        rows_to_insert=rows_to_insert,
                        batch_start=batch_start,
                        avg_lines_per_order=args.avg_lines_per_order,
                        start_date=start_date,
                        date_span=date_span,
                        event_sample_percent=args.event_sample_percent,
                    )
                    insert_event_batch(
                        cur,
                        table_name="payment_status_event",
                        status_column="payment_status",
                        case_sql="""
                            CASE rn %% 4
                                WHEN 0 THEN 'paid'
                                WHEN 1 THEN 'paid'
                                WHEN 2 THEN 'pending'
                                ELSE 'failed'
                            END
                        """,
                        event_ts_offset_sql="event_ts + INTERVAL '30 minutes'",
                        rows_to_insert=rows_to_insert,
                        batch_start=batch_start,
                        avg_lines_per_order=args.avg_lines_per_order,
                        start_date=start_date,
                        date_span=date_span,
                        event_sample_percent=args.event_sample_percent,
                    )

                conn.commit()
                current_rows += rows_to_insert
                inserted_total += rows_to_insert
                print(
                    f"Inserted {inserted_total:,}/{args.target_sales_rows:,} synthetic sales rows. "
                    f"Current sales_order_line row count: {current_rows:,}"
                )

            with conn.cursor() as analyze_cur:
                analyze_cur.execute("ANALYZE retail_oi.sales_order_line;")
                analyze_cur.execute("ANALYZE retail_oi.order_status_event;")
                analyze_cur.execute("ANALYZE retail_oi.shipment_status_event;")
                analyze_cur.execute("ANALYZE retail_oi.payment_status_event;")
            conn.commit()

            print("Scale generation complete.")


if __name__ == "__main__":
    main()
