import argparse
import math
import os
import random
import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone

import psycopg


REQUIRED_TABLES = {
    "retail_oi.customer_master",
    "retail_oi.product_master",
    "retail_oi.sales_order_line",
    "retail_oi.order_status_event",
    "retail_oi.shipment_status_event",
    "retail_oi.payment_status_event",
    "retail_oi.source_simulation_run",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate PostgreSQL incremental source changes.")
    parser.add_argument("--dsn", default=os.environ.get("POSTGRES_DSN"),
                        required=not bool(os.environ.get("POSTGRES_DSN")),
                        help="PostgreSQL DSN; defaults to POSTGRES_DSN. Use a disposable source.")
    parser.add_argument("--inserted-sales-count", type=int, default=1200)
    parser.add_argument("--updated-sales-count", type=int, default=250)
    parser.add_argument("--event-count", type=int, default=500)
    parser.add_argument("--dirty-data-rate", type=float, default=0.005, help="Fraction of touched rows to dirty.")
    parser.add_argument("--run-date", help="UTC date override in YYYY-MM-DD format. Ignored when --run-timestamp is supplied.")
    parser.add_argument("--run-timestamp", help="UTC timestamp override in ISO-8601 format.")
    parser.add_argument("--avg-lines-per-order", type=int, default=3)
    return parser.parse_args()


def scalar(cur: psycopg.Cursor, sql: str, params: dict | None = None):
    cur.execute(sql, params or {})
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


def ensure_run_log_columns(cur: psycopg.Cursor) -> None:
    statements = [
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS run_id UUID",
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS run_started_ts TIMESTAMPTZ(3)",
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS run_completed_ts TIMESTAMPTZ(3)",
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS run_timestamp TIMESTAMPTZ(3)",
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS event_count_requested INT",
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS inserted_sales_rows INT",
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS updated_sales_rows INT",
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS inserted_order_events INT",
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS inserted_shipment_events INT",
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS inserted_payment_events INT",
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS dirty_rows_injected INT",
        "ALTER TABLE retail_oi.source_simulation_run ADD COLUMN IF NOT EXISTS status VARCHAR(30)",
    ]
    for sql in statements:
        cur.execute(sql)


def dirty_rate_to_per_10000(rate: float) -> int:
    if rate <= 1:
        return int(rate * 10000)
    return int(rate)


def parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def to_base36(value: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if value < 0:
        raise ValueError("Base36 conversion requires a non-negative integer")
    if value == 0:
        return "0"

    digits: list[str] = []
    remaining = value
    while remaining:
        remaining, remainder = divmod(remaining, 36)
        digits.append(alphabet[remainder])
    return "".join(reversed(digits))


def build_order_number(run_ts: datetime, run_id: uuid.UUID, order_index: int) -> str:
    run_component = to_base36(int(run_ts.timestamp())).zfill(7)[-7:]
    run_seed = run_id.hex[:4].upper()
    order_component = to_base36(order_index).zfill(5)[-5:]
    order_number = f"PG{run_component}{run_seed}{order_component}"
    if len(order_number) > 20:
        raise ValueError(f"Generated order_number exceeds VARCHAR(20): {order_number}")
    return order_number


def build_lookup_lists(cur: psycopg.Cursor) -> tuple[list[int], list[tuple[str, float]]]:
    cur.execute("SELECT customer_id FROM retail_oi.customer_master ORDER BY customer_id")
    customers = [row[0] for row in cur.fetchall()]
    cur.execute(
        """
        SELECT product_business_key, COALESCE(NULLIF(product_cost, 0), 25.00)::float
        FROM retail_oi.product_master
        ORDER BY product_key
        """
    )
    products = [(row[0], float(row[1])) for row in cur.fetchall()]
    if not customers or not products:
        raise RuntimeError("customer_master and product_master must be populated before simulation")
    return customers, products


def create_run_log(cur: psycopg.Cursor, args: argparse.Namespace, run_id: uuid.UUID, run_ts: datetime) -> int:
    cur.execute(
        """
        INSERT INTO retail_oi.source_simulation_run (
            run_date,
            started_at,
            new_rows_requested,
            existing_update_rows,
            late_arriving_rows,
            duplicate_rows,
            dirty_rate_per_10000,
            event_sample_percent,
            run_status,
            dwh_load_ts,
            run_id,
            run_started_ts,
            run_timestamp,
            event_count_requested,
            status
        )
        VALUES (
            %s::date,
            %s,
            %s,
            %s,
            0,
            0,
            %s,
            0,
            'running',
            %s,
            %s,
            %s,
            %s,
            %s,
            'running'
        )
        RETURNING simulation_run_key
        """,
        (
            run_ts.date(),
            run_ts,
            args.inserted_sales_count,
            args.updated_sales_count,
            dirty_rate_to_per_10000(args.dirty_data_rate),
            run_ts,
            run_id,
            run_ts,
            run_ts,
            args.event_count,
        ),
    )
    return cur.fetchone()[0]


def fetch_random_sales_rows(cur: psycopg.Cursor, target_count: int, rng: random.Random) -> list[dict]:
    max_key = scalar(cur, "SELECT MAX(sales_key) FROM retail_oi.sales_order_line")
    if not max_key:
        return []

    collected: dict[int, dict] = {}
    attempts = 0
    while len(collected) < target_count and attempts < 10:
        attempts += 1
        sample_size = max(target_count * 3, 500)
        candidate_keys = [rng.randint(1, max_key) for _ in range(sample_size)]
        cur.execute(
            """
            SELECT sales_key, order_number, order_date, ship_date, due_date, quantity, unit_price, sales_amount
            FROM retail_oi.sales_order_line
            WHERE sales_key = ANY(%s)
            """,
            (candidate_keys,),
        )
        for row in cur.fetchall():
            collected[row[0]] = {
                "sales_key": row[0],
                "order_number": row[1],
                "order_date": row[2],
                "ship_date": row[3],
                "due_date": row[4],
                "quantity": row[5],
                "unit_price": float(row[6]),
                "sales_amount": float(row[7]),
            }

    return list(collected.values())[:target_count]


def build_new_sales_rows(
    *,
    count: int,
    avg_lines_per_order: int,
    customers: Sequence[int],
    products: Sequence[tuple[str, float]],
    run_ts: datetime,
    run_id: uuid.UUID,
    rng: random.Random,
) -> list[tuple]:
    rows: list[tuple] = []
    order_count = max(1, math.ceil(count / avg_lines_per_order))
    order_numbers = [build_order_number(run_ts, run_id, index) for index in range(1, order_count + 1)]
    # Header attributes are chosen once per order. Varying these by line made
    # one business order appear to belong to several customers and dates.
    order_customers = [customers[rng.randrange(len(customers))] for _ in range(order_count)]
    order_dates = [(run_ts - timedelta(days=rng.randint(0, 14))).date() for _ in range(order_count)]

    for line_number in range(count):
        order_index = min(line_number // avg_lines_per_order, order_count - 1)
        order_number = order_numbers[order_index]
        customer_id = order_customers[order_index]
        product_business_key, base_price = products[
            (line_number * 53 + rng.randint(0, len(products) - 1)) % len(products)
        ]
        order_date = order_dates[order_index]
        quantity = rng.randint(1, 5)
        unit_price = round(base_price * (1.08 + (rng.randint(0, 30) / 100.0)), 2)
        sales_amount = round(quantity * unit_price, 2)
        ship_date = order_date + timedelta(days=rng.randint(1, 5))
        due_date = order_date + timedelta(days=rng.randint(3, 8))
        rows.append(
            (
                order_number,
                product_business_key,
                customer_id,
                order_date,
                ship_date,
                due_date,
                sales_amount,
                quantity,
                unit_price,
                run_ts,
                "pg_sim",
            )
        )
    return rows


def insert_new_sales(cur: psycopg.Cursor, rows: Sequence[tuple]) -> list[dict]:
    if not rows:
        return []

    run_ts = rows[0][9]
    order_numbers = list(dict.fromkeys(row[0] for row in rows))

    cur.executemany(
        """
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )

    cur.execute(
        """
        SELECT sales_key, order_number, order_date, ship_date, due_date, quantity, unit_price, sales_amount
        FROM retail_oi.sales_order_line
        WHERE dwh_load_ts = %s
          AND dwh_source_system = 'pg_sim'
          AND order_number = ANY(%s)
        ORDER BY sales_key
        """,
        (run_ts, order_numbers),
    )
    inserted = []
    for row in cur.fetchall():
        inserted.append(
            {
                "sales_key": row[0],
                "order_number": row[1],
                "order_date": row[2],
                "ship_date": row[3],
                "due_date": row[4],
                "quantity": row[5],
                "unit_price": float(row[6]),
                "sales_amount": float(row[7]),
            }
        )
    # Persist the order-to-customer/date contract in the source transaction.
    # DISTINCT ON takes the first line only; every generated line already uses
    # the same header attributes, so later lines cannot redefine the order.
    cur.execute(
        """
        INSERT INTO retail_oi.order_header (
            order_number, anchor_sales_key, customer_id, order_date,
            ship_date, due_date, dwh_load_ts, dwh_source_system,
            order_status, shipment_status, payment_status, status_updated_ts
        )
        SELECT DISTINCT ON (order_number)
            order_number, sales_key, customer_id, order_date,
            ship_date, due_date, dwh_load_ts, dwh_source_system,
            'created', 'pending', 'pending', %s
        FROM retail_oi.sales_order_line
        WHERE dwh_load_ts = %s
          AND dwh_source_system = 'pg_sim'
          AND order_number = ANY(%s)
        ORDER BY order_number, sales_key
        ON CONFLICT (order_number) DO NOTHING
        """,
        (run_ts, run_ts, order_numbers),
    )
    return inserted


def update_existing_sales(cur: psycopg.Cursor, rows: Sequence[dict], run_ts: datetime, rng: random.Random) -> int:
    """Revise line prices without changing order-level header attributes."""
    updated = 0
    for row in rows:
        unit_price = round(row["unit_price"] * (1.01 + rng.randint(0, 4) / 100.0), 2)
        sales_amount = round(row["quantity"] * unit_price, 2)

        cur.execute(
            """
            UPDATE retail_oi.sales_order_line
            SET
                unit_price = %s,
                sales_amount = %s,
                dwh_load_ts = %s
            WHERE sales_key = %s
            """,
            (unit_price, sales_amount, run_ts, row["sales_key"]),
        )
        updated += cur.rowcount
    return updated


def inject_dirty_updates(
    cur: psycopg.Cursor,
    inserted_rows: list[dict],
    updated_rows: list[dict],
    dirty_rows_target: int,
    run_ts: datetime,
    rng: random.Random,
) -> tuple[int, int]:
    if dirty_rows_target <= 0:
        return 0, 0

    dirty_updates = 0
    duplicate_rows = 0
    target_rows = inserted_rows[:]
    rng.shuffle(target_rows)

    if target_rows:
        dirty_sample = target_rows[: max(0, dirty_rows_target - 1)]
        for index, row in enumerate(dirty_sample):
            if index % 3 == 0:
                cur.execute(
                    """
                    UPDATE retail_oi.sales_order_line
                    SET ship_date = order_date - INTERVAL '1 day', dwh_load_ts = %s
                    WHERE sales_key = %s
                    """,
                    (run_ts, row["sales_key"]),
                )
            elif index % 3 == 1:
                cur.execute(
                    """
                    UPDATE retail_oi.sales_order_line
                    SET due_date = order_date - INTERVAL '1 day', dwh_load_ts = %s
                    WHERE sales_key = %s
                    """,
                    (run_ts, row["sales_key"]),
                )
            else:
                cur.execute(
                    """
                    UPDATE retail_oi.sales_order_line
                    SET sales_amount = sales_amount + 7.00, dwh_load_ts = %s
                    WHERE sales_key = %s
                    """,
                    (run_ts, row["sales_key"]),
                )
            dirty_updates += cur.rowcount

        duplicate_source = dirty_sample[0] if dirty_sample else target_rows[0]
        cur.execute(
            """
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
                %s,
                'pg_sim'
            FROM retail_oi.sales_order_line
            WHERE sales_key = %s
            """,
            (run_ts, duplicate_source["sales_key"]),
        )
        duplicate_rows = cur.rowcount

    return dirty_updates, duplicate_rows


def fetch_existing_order_numbers(cur: psycopg.Cursor, count: int, rng: random.Random) -> list[str]:
    max_key = scalar(cur, "SELECT MAX(sales_key) FROM retail_oi.sales_order_line")
    if not max_key or count <= 0:
        return []
    order_numbers: dict[str, None] = {}
    while len(order_numbers) < count:
        candidate_keys = [rng.randint(1, max_key) for _ in range(max(count * 3, 300))]
        cur.execute(
            "SELECT DISTINCT order_number FROM retail_oi.sales_order_line WHERE sales_key = ANY(%s)",
            (candidate_keys,),
        )
        for row in cur.fetchall():
            order_numbers[row[0]] = None
            if len(order_numbers) >= count:
                break
    return list(order_numbers.keys())[:count]


def build_event_orders(
    *,
    new_order_numbers: list[str],
    updated_order_numbers: list[str],
    cur: psycopg.Cursor,
    event_count: int,
    rng: random.Random,
) -> list[str]:
    ordered_unique = list(dict.fromkeys(new_order_numbers + updated_order_numbers))
    if len(ordered_unique) >= event_count:
        return ordered_unique[:event_count]

    extras = fetch_existing_order_numbers(cur, event_count - len(ordered_unique), rng)
    return list(dict.fromkeys(ordered_unique + extras))[:event_count]


def insert_events(
    cur: psycopg.Cursor,
    *,
    table_name: str,
    status_column: str,
    event_orders: Sequence[str],
    states: dict[str, tuple[str, str, str]],
    status_index: int,
    run_ts: datetime,
    event_offset_minutes: int,
    rng: random.Random,
) -> int:
    rows = []
    for index, order_number in enumerate(event_orders):
        event_ts = run_ts + timedelta(minutes=event_offset_minutes + index % 180)
        rows.append((order_number, states[order_number][status_index], event_ts, run_ts, "pg_sim"))

    cur.executemany(
        f"""
        INSERT INTO retail_oi.{table_name} (
            order_number,
            {status_column},
            event_ts,
            dwh_load_ts,
            dwh_source_system
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        rows,
    )
    return len(rows)


def build_order_states(cur: psycopg.Cursor, event_orders: Sequence[str], rng: random.Random) -> dict[str, tuple[str, str, str]]:
    """Choose valid, non-regressing order transitions and aligned source states."""
    if not event_orders:
        return {}
    cur.execute(
        "SELECT order_number, order_status FROM retail_oi.order_header WHERE order_number = ANY(%s)",
        (list(event_orders),),
    )
    current = dict(cur.fetchall())
    if len(current) != len(event_orders):
        raise RuntimeError("Every simulated event order must have an order_header row")
    transitions = {
        "created": ("created", "packed", "shipped", "cancelled"),
        "packed": ("packed", "shipped", "cancelled"),
        "shipped": ("shipped", "delivered"),
        "delivered": ("delivered", "returned"),
        "cancelled": ("cancelled",),
        "returned": ("returned",),
    }
    states: dict[str, tuple[str, str, str]] = {}
    for order_number in event_orders:
        possible = transitions.get(current[order_number])
        if possible is None:
            raise RuntimeError(f"Unsupported order status for {order_number}: {current[order_number]}")
        order_status = rng.choice(possible)
        if order_status == "shipped":
            states[order_number] = (order_status, rng.choice(("in_transit", "delayed")), "paid")
        elif order_status == "delivered":
            states[order_number] = (order_status, "delivered", "paid")
        elif order_status == "returned":
            states[order_number] = (order_status, "delivered", "refunded")
        elif order_status == "cancelled":
            states[order_number] = (order_status, "pending", rng.choice(("failed", "refunded")))
        elif order_status == "packed":
            states[order_number] = (order_status, "pending", rng.choice(("pending", "paid")))
        else:
            states[order_number] = (order_status, "pending", "pending")
    return states


def update_order_headers(
    cur: psycopg.Cursor,
    event_orders: Sequence[str],
    states: dict[str, tuple[str, str, str]],
    run_ts: datetime,
) -> None:
    """Publish the same latest state as the event triplet, with a new watermark."""
    rows = []
    for index, order_number in enumerate(event_orders):
        order_status, shipment_status, payment_status = states[order_number]
        shipment_ts = run_ts + timedelta(minutes=15 + index % 180)
        payment_ts = run_ts + timedelta(minutes=30 + index % 180)
        rows.append((
            order_status, shipment_status, payment_status,
            shipment_ts if order_status in ("delivered", "returned") else None,
            payment_ts if payment_status in ("paid", "refunded") else None,
            payment_ts, run_ts, order_number,
        ))
    cur.executemany(
        """
        UPDATE retail_oi.order_header
        SET order_status = %s, shipment_status = %s, payment_status = %s,
            delivered_ts = COALESCE(%s, delivered_ts),
            payment_ts = COALESCE(%s, payment_ts),
            status_updated_ts = %s, dwh_load_ts = %s
        WHERE order_number = %s
        """,
        rows,
    )


def finalize_run_log(
    cur: psycopg.Cursor,
    *,
    simulation_run_key: int,
    run_ts: datetime,
    inserted_sales_rows: int,
    updated_sales_rows: int,
    inserted_order_events: int,
    inserted_shipment_events: int,
    inserted_payment_events: int,
    dirty_rows_injected: int,
    late_arriving_rows: int,
    duplicate_rows: int,
    status: str,
    error_message: str | None,
) -> None:
    cur.execute(
        """
        UPDATE retail_oi.source_simulation_run
        SET
            completed_at = %s,
            rows_inserted = %s,
            rows_updated = %s,
            order_events_inserted = %s,
            shipment_events_inserted = %s,
            payment_events_inserted = %s,
            run_status = %s,
            error_message = %s,
            dwh_load_ts = %s,
            late_arriving_rows = %s,
            duplicate_rows = %s,
            run_completed_ts = %s,
            inserted_sales_rows = %s,
            updated_sales_rows = %s,
            inserted_order_events = %s,
            inserted_shipment_events = %s,
            inserted_payment_events = %s,
            dirty_rows_injected = %s,
            status = %s
        WHERE simulation_run_key = %s
        """,
        (
            run_ts,
            inserted_sales_rows,
            updated_sales_rows,
            inserted_order_events,
            inserted_shipment_events,
            inserted_payment_events,
            status,
            error_message,
            run_ts,
            late_arriving_rows,
            duplicate_rows,
            run_ts,
            inserted_sales_rows,
            updated_sales_rows,
            inserted_order_events,
            inserted_shipment_events,
            inserted_payment_events,
            dirty_rows_injected,
            status,
            simulation_run_key,
        ),
    )


def main() -> None:
    args = parse_args()
    if args.inserted_sales_count < 0:
        raise ValueError("--inserted-sales-count must be greater than or equal to zero")
    if args.updated_sales_count < 0:
        raise ValueError("--updated-sales-count must be greater than or equal to zero")
    if args.event_count < 0:
        raise ValueError("--event-count must be greater than or equal to zero")
    if args.avg_lines_per_order <= 0:
        raise ValueError("--avg-lines-per-order must be greater than zero")
    if args.dirty_data_rate < 0:
        raise ValueError("--dirty-data-rate must be greater than or equal to zero")

    if args.run_timestamp:
        run_ts = parse_utc_timestamp(args.run_timestamp)
    elif args.run_date:
        run_dt = date.fromisoformat(args.run_date)
        run_ts = datetime.combine(run_dt, datetime.min.time(), tzinfo=timezone.utc)
    else:
        run_ts = datetime.now(timezone.utc).replace(microsecond=0)

    rng = random.Random(run_ts.isoformat())
    run_id = uuid.uuid4()

    with psycopg.connect(args.dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            ensure_required_tables(cur)
            ensure_run_log_columns(cur)
            customers, products = build_lookup_lists(cur)
            simulation_run_key = create_run_log(cur, args, run_id, run_ts)
            conn.commit()

            try:
                new_rows = build_new_sales_rows(
                    count=args.inserted_sales_count,
                    avg_lines_per_order=args.avg_lines_per_order,
                    customers=customers,
                    products=products,
                    run_ts=run_ts,
                    run_id=run_id,
                    rng=rng,
                )
                inserted_rows = insert_new_sales(cur, new_rows)
                rows_to_update = fetch_random_sales_rows(cur, args.updated_sales_count, rng)
                updated_count = update_existing_sales(cur, rows_to_update, run_ts, rng)
                late_arriving_rows = sum(1 for row in inserted_rows if row["order_date"] < run_ts.date())

                dirty_target = max(1, int((args.inserted_sales_count + args.updated_sales_count) * args.dirty_data_rate)) if args.dirty_data_rate > 0 else 0
                dirty_updates, duplicate_rows = inject_dirty_updates(
                    cur,
                    inserted_rows=inserted_rows,
                    updated_rows=rows_to_update,
                    dirty_rows_target=dirty_target,
                    run_ts=run_ts,
                    rng=rng,
                )

                new_order_numbers = [row["order_number"] for row in inserted_rows]
                updated_order_numbers = [row["order_number"] for row in rows_to_update]
                event_orders = build_event_orders(
                    new_order_numbers=new_order_numbers,
                    updated_order_numbers=updated_order_numbers,
                    cur=cur,
                    event_count=args.event_count,
                    rng=rng,
                )
                states = build_order_states(cur, event_orders, rng)

                inserted_order_events = insert_events(
                    cur,
                    table_name="order_status_event",
                    status_column="event_status",
                    event_orders=event_orders,
                    states=states,
                    status_index=0,
                    run_ts=run_ts,
                    event_offset_minutes=0,
                    rng=rng,
                )
                inserted_shipment_events = insert_events(
                    cur,
                    table_name="shipment_status_event",
                    status_column="shipment_status",
                    event_orders=event_orders,
                    states=states,
                    status_index=1,
                    run_ts=run_ts,
                    event_offset_minutes=15,
                    rng=rng,
                )
                inserted_payment_events = insert_events(
                    cur,
                    table_name="payment_status_event",
                    status_column="payment_status",
                    event_orders=event_orders,
                    states=states,
                    status_index=2,
                    run_ts=run_ts,
                    event_offset_minutes=30,
                    rng=rng,
                )

                update_order_headers(cur, event_orders, states, run_ts)

                finalize_run_log(
                    cur,
                    simulation_run_key=simulation_run_key,
                    run_ts=run_ts,
                    inserted_sales_rows=len(inserted_rows) + duplicate_rows,
                    updated_sales_rows=updated_count,
                    inserted_order_events=inserted_order_events,
                    inserted_shipment_events=inserted_shipment_events,
                    inserted_payment_events=inserted_payment_events,
                    dirty_rows_injected=dirty_updates + duplicate_rows,
                    late_arriving_rows=late_arriving_rows,
                    duplicate_rows=duplicate_rows,
                    status="succeeded",
                    error_message=None,
                )
                conn.commit()
            except Exception as exc:  # pragma: no cover - operational path
                conn.rollback()
                with conn.cursor() as log_cur:
                    finalize_run_log(
                        log_cur,
                        simulation_run_key=simulation_run_key,
                        run_ts=datetime.now(timezone.utc).replace(microsecond=0),
                        inserted_sales_rows=0,
                        updated_sales_rows=0,
                        inserted_order_events=0,
                        inserted_shipment_events=0,
                        inserted_payment_events=0,
                        dirty_rows_injected=0,
                        late_arriving_rows=0,
                        duplicate_rows=0,
                        status="failed",
                        error_message=str(exc),
                    )
                    conn.commit()
                raise

    print(f"Simulation run {run_id} completed at {run_ts.isoformat()}")
    print(
        f"Inserted sales: {len(inserted_rows) + duplicate_rows:,}, "
        f"updated sales: {updated_count:,}, "
        f"order events: {inserted_order_events:,}, "
        f"shipment events: {inserted_shipment_events:,}, "
        f"payment events: {inserted_payment_events:,}, "
        f"dirty rows injected: {dirty_updates + duplicate_rows:,}"
    )


if __name__ == "__main__":
    main()
