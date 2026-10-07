import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

import psycopg


COUNTRY_CANONICAL = {
    "united states": "United States",
    "usa": "United States",
    "us": "United States",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "great britain": "United Kingdom",
    "britain": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "germany": "Germany",
    "de": "Germany",
    "france": "France",
    "fr": "France",
    "canada": "Canada",
    "ca": "Canada",
    "australia": "Australia",
    "au": "Australia",
}


def canonical_country(raw_country: str | None) -> str | None:
    if raw_country is None:
        return None
    cleaned = raw_country.strip()
    if cleaned == "":
        return None
    return COUNTRY_CANONICAL.get(cleaned.lower(), cleaned)


def stable_slot(key: str, size: int) -> int:
    digest = hashlib.md5(key.encode("utf-8"), usedforsecurity=False).hexdigest()
    return int(digest[:12], 16) % size


def load_location_master(path: Path) -> tuple[list[str], dict[str, list[dict[str, str]]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    countries = sorted({row["country"] for row in rows})
    by_country: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_country[row["country"]].append(row)
    return countries, by_country


def choose_location(
    customer_id: int,
    customer_business_key: str | None,
    raw_country: str | None,
    countries: list[str],
    locations_by_country: dict[str, list[dict[str, str]]],
) -> tuple[str, dict[str, str]]:
    canonical = canonical_country(raw_country)
    identity = customer_business_key or f"customer-{customer_id}"

    if canonical not in locations_by_country:
        canonical = countries[stable_slot(identity + "-country", len(countries))]

    country_locations = locations_by_country[canonical]
    row = country_locations[stable_slot(identity + "-location", len(country_locations))]
    return canonical, row


def main() -> None:
    parser = argparse.ArgumentParser(description="Align PostgreSQL customer geography to the S3 location master.")
    parser.add_argument("--dsn", required=True, help="PostgreSQL connection string.")
    parser.add_argument(
        "--location-master-path",
        default="datasets/s3_reference/location_master/location_master.csv",
        help="Local location_master.csv path.",
    )
    args = parser.parse_args()

    location_master_path = Path(args.location_master_path).expanduser().resolve()
    if not location_master_path.exists():
        raise FileNotFoundError(f"Missing location master file: {location_master_path}")

    countries, locations_by_country = load_location_master(location_master_path)

    with psycopg.connect(args.dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT customer_key, customer_id, customer_business_key, country
                FROM retail_oi.customer_master
                ORDER BY customer_key;
                """
            )
            customers = cur.fetchall()

            updates = []
            for customer_key, customer_id, customer_business_key, raw_country in customers:
                canonical, location = choose_location(
                    customer_id=customer_id,
                    customer_business_key=customer_business_key,
                    raw_country=raw_country,
                    countries=countries,
                    locations_by_country=locations_by_country,
                )
                updates.append(
                    (
                        canonical,
                        location["state_province"],
                        location["city"],
                        location["postal_code"],
                        customer_key,
                    )
                )

            cur.executemany(
                """
                UPDATE retail_oi.customer_master
                SET
                    country = %s,
                    state_province = %s,
                    city = %s,
                    postal_code = %s,
                    dwh_load_ts = NOW()
                WHERE customer_key = %s;
                """,
                updates,
            )
        conn.commit()

    print(f"Aligned {len(updates):,} customer_master rows to S3 location geography.")


if __name__ == "__main__":
    main()
