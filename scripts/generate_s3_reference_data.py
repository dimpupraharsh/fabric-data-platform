import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path


LOCATION_COLUMNS = [
    "location_id",
    "country",
    "region",
    "subregion",
    "state_province",
    "city",
    "postal_code",
    "timezone",
    "market_area",
    "is_active",
    "effective_from",
    "effective_to",
]

DELIVERY_ZONE_COLUMNS = [
    "postal_code",
    "delivery_zone",
    "zone_priority",
    "standard_sla_days",
    "express_sla_days",
    "remote_area_flag",
    "serviceability_flag",
    "last_updated_date",
]

WAREHOUSE_COVERAGE_COLUMNS = [
    "warehouse_id",
    "warehouse_name",
    "warehouse_country",
    "service_region",
    "covered_country",
    "covered_region",
    "covered_postal_code",
    "delivery_type",
    "serviceability_flag",
    "max_sla_days",
    "last_updated_date",
]

GEO_HIERARCHY_COLUMNS = [
    "country",
    "country_code",
    "region",
    "region_code",
    "subregion",
    "market",
    "sales_territory",
    "active_flag",
    "last_updated_date",
]

CITY_SEEDS = [
    # United States
    ("United States", "US", "Northeast", "US-NE", "Atlantic", "New York", "New York", "America/New_York", "North America", "NA-East", "100"),
    ("United States", "US", "Northeast", "US-NE", "New England", "Massachusetts", "Boston", "America/New_York", "North America", "NA-East", "021"),
    ("United States", "US", "South", "US-SO", "Southeast", "Georgia", "Atlanta", "America/New_York", "North America", "NA-South", "303"),
    ("United States", "US", "South", "US-SO", "Texas", "Texas", "Dallas", "America/Chicago", "North America", "NA-South", "752"),
    ("United States", "US", "Midwest", "US-MW", "Great Lakes", "Illinois", "Chicago", "America/Chicago", "North America", "NA-Central", "606"),
    ("United States", "US", "Midwest", "US-MW", "Upper Midwest", "Minnesota", "Minneapolis", "America/Chicago", "North America", "NA-Central", "554"),
    ("United States", "US", "West", "US-WE", "Pacific", "California", "Los Angeles", "America/Los_Angeles", "North America", "NA-West", "900"),
    ("United States", "US", "West", "US-WE", "Pacific", "California", "San Francisco", "America/Los_Angeles", "North America", "NA-West", "941"),
    ("United States", "US", "West", "US-WE", "Mountain", "Colorado", "Denver", "America/Denver", "North America", "NA-West", "802"),
    ("United States", "US", "West", "US-WE", "Pacific Northwest", "Washington", "Seattle", "America/Los_Angeles", "North America", "NA-West", "981"),
    # Canada
    ("Canada", "CA", "Central Canada", "CA-CC", "Ontario Corridor", "Ontario", "Toronto", "America/Toronto", "North America", "CA-East", "M5"),
    ("Canada", "CA", "Central Canada", "CA-CC", "Ontario Corridor", "Ontario", "Ottawa", "America/Toronto", "North America", "CA-East", "K1"),
    ("Canada", "CA", "Quebec", "CA-QC", "St Lawrence", "Quebec", "Montreal", "America/Toronto", "North America", "CA-East", "H2"),
    ("Canada", "CA", "Western Canada", "CA-WC", "Prairies", "Alberta", "Calgary", "America/Edmonton", "North America", "CA-West", "T2"),
    ("Canada", "CA", "Western Canada", "CA-WC", "Pacific", "British Columbia", "Vancouver", "America/Vancouver", "North America", "CA-West", "V6"),
    ("Canada", "CA", "Atlantic Canada", "CA-AC", "Maritimes", "Nova Scotia", "Halifax", "America/Halifax", "North America", "CA-East", "B3"),
    # United Kingdom
    ("United Kingdom", "GB", "England", "GB-ENG", "Greater London", "England", "London", "Europe/London", "Europe", "UK-South", "SW1A"),
    ("United Kingdom", "GB", "England", "GB-ENG", "North West", "England", "Manchester", "Europe/London", "Europe", "UK-North", "M1"),
    ("United Kingdom", "GB", "England", "GB-ENG", "West Midlands", "England", "Birmingham", "Europe/London", "Europe", "UK-Midlands", "B1"),
    ("United Kingdom", "GB", "Scotland", "GB-SCT", "Central Belt", "Scotland", "Glasgow", "Europe/London", "Europe", "UK-North", "G1"),
    ("United Kingdom", "GB", "Scotland", "GB-SCT", "Lothian", "Scotland", "Edinburgh", "Europe/London", "Europe", "UK-North", "EH1"),
    ("United Kingdom", "GB", "Wales", "GB-WLS", "South Wales", "Wales", "Cardiff", "Europe/London", "Europe", "UK-West", "CF10"),
    # France
    ("France", "FR", "Ile-de-France", "FR-IDF", "Paris Basin", "Ile-de-France", "Paris", "Europe/Paris", "Europe", "FR-North", "750"),
    ("France", "FR", "Auvergne-Rhone-Alpes", "FR-ARA", "Rhone Valley", "Auvergne-Rhone-Alpes", "Lyon", "Europe/Paris", "Europe", "FR-East", "690"),
    ("France", "FR", "Provence-Alpes-Cote d'Azur", "FR-PAC", "Mediterranean", "Provence-Alpes-Cote d'Azur", "Marseille", "Europe/Paris", "Europe", "FR-South", "130"),
    ("France", "FR", "Occitanie", "FR-OCC", "Garonne", "Occitanie", "Toulouse", "Europe/Paris", "Europe", "FR-South", "310"),
    ("France", "FR", "Nouvelle-Aquitaine", "FR-NAQ", "Atlantic", "Nouvelle-Aquitaine", "Bordeaux", "Europe/Paris", "Europe", "FR-West", "330"),
    ("France", "FR", "Hauts-de-France", "FR-HDF", "Flanders", "Hauts-de-France", "Lille", "Europe/Paris", "Europe", "FR-North", "590"),
    # Germany
    ("Germany", "DE", "North Rhine-Westphalia", "DE-NW", "Rhine-Ruhr", "North Rhine-Westphalia", "Cologne", "Europe/Berlin", "Europe", "DE-West", "506"),
    ("Germany", "DE", "Bavaria", "DE-BY", "Upper Bavaria", "Bavaria", "Munich", "Europe/Berlin", "Europe", "DE-South", "803"),
    ("Germany", "DE", "Berlin", "DE-BE", "Berlin-Brandenburg", "Berlin", "Berlin", "Europe/Berlin", "Europe", "DE-East", "101"),
    ("Germany", "DE", "Hesse", "DE-HE", "Main Region", "Hesse", "Frankfurt", "Europe/Berlin", "Europe", "DE-Central", "603"),
    ("Germany", "DE", "Hamburg", "DE-HH", "North Sea", "Hamburg", "Hamburg", "Europe/Berlin", "Europe", "DE-North", "200"),
    ("Germany", "DE", "Saxony", "DE-SN", "Elbe", "Saxony", "Dresden", "Europe/Berlin", "Europe", "DE-East", "010"),
    # Australia
    ("Australia", "AU", "New South Wales", "AU-NSW", "Greater Sydney", "New South Wales", "Sydney", "Australia/Sydney", "Asia Pacific", "AU-East", "200"),
    ("Australia", "AU", "Victoria", "AU-VIC", "Greater Melbourne", "Victoria", "Melbourne", "Australia/Melbourne", "Asia Pacific", "AU-South", "300"),
    ("Australia", "AU", "Queensland", "AU-QLD", "South East Queensland", "Queensland", "Brisbane", "Australia/Brisbane", "Asia Pacific", "AU-North", "400"),
    ("Australia", "AU", "Western Australia", "AU-WA", "Greater Perth", "Western Australia", "Perth", "Australia/Perth", "Asia Pacific", "AU-West", "600"),
    ("Australia", "AU", "South Australia", "AU-SA", "Greater Adelaide", "South Australia", "Adelaide", "Australia/Adelaide", "Asia Pacific", "AU-South", "500"),
    ("Australia", "AU", "Australian Capital Territory", "AU-ACT", "Capital Region", "Australian Capital Territory", "Canberra", "Australia/Sydney", "Asia Pacific", "AU-East", "260"),
]

WAREHOUSES = {
    "United States": [
        ("wh_us_east_01", "Newark Metro Fulfillment", "Northeast"),
        ("wh_us_south_01", "Dallas Regional Fulfillment", "South"),
        ("wh_us_central_01", "Chicago Crossdock", "Midwest"),
        ("wh_us_west_01", "Los Angeles Fulfillment", "West"),
    ],
    "Canada": [
        ("wh_ca_east_01", "Toronto Fulfillment", "Central Canada"),
        ("wh_ca_west_01", "Vancouver Fulfillment", "Western Canada"),
        ("wh_ca_atl_01", "Halifax Forward Stock", "Atlantic Canada"),
    ],
    "United Kingdom": [
        ("wh_uk_south_01", "Milton Keynes Fulfillment", "England"),
        ("wh_uk_north_01", "Manchester Fulfillment", "England"),
        ("wh_uk_scot_01", "Glasgow Forward Stock", "Scotland"),
    ],
    "France": [
        ("wh_fr_north_01", "Paris Fulfillment", "Ile-de-France"),
        ("wh_fr_south_01", "Lyon-Marseille Fulfillment", "Auvergne-Rhone-Alpes"),
        ("wh_fr_west_01", "Bordeaux Forward Stock", "Nouvelle-Aquitaine"),
    ],
    "Germany": [
        ("wh_de_west_01", "Cologne Fulfillment", "North Rhine-Westphalia"),
        ("wh_de_south_01", "Munich Fulfillment", "Bavaria"),
        ("wh_de_east_01", "Berlin Forward Stock", "Berlin"),
    ],
    "Australia": [
        ("wh_au_east_01", "Sydney Fulfillment", "New South Wales"),
        ("wh_au_south_01", "Melbourne Fulfillment", "Victoria"),
        ("wh_au_west_01", "Perth Forward Stock", "Western Australia"),
    ],
}


def postal_code(country_code: str, seed: str, index: int) -> str:
    if country_code in {"US", "FR", "DE"}:
        return f"{country_code}-{seed}{index:03d}"
    if country_code == "AU":
        return f"AU-{int(seed):04d}-{index:03d}"
    if country_code == "CA":
        return f"CA-{seed}{index:03d}"
    if country_code == "GB":
        return f"GB-{seed}-{index:03d}"
    raise ValueError(f"Unhandled country_code: {country_code}")


def delivery_profile(region: str, city: str, row_number: int) -> tuple[str, int, int, int, bool, bool]:
    remote_city = city in {"Perth", "Halifax", "Dresden", "Cardiff", "Canberra"}
    remote = remote_city or row_number % 47 == 0
    serviceable = row_number % 173 != 0
    if remote:
        return "remote", 4, 5, 3, True, serviceable
    if region in {"West", "Western Canada", "Western Australia"}:
        return "regional", 3, 4, 2, False, serviceable
    if region in {"Northeast", "England", "Ile-de-France", "North Rhine-Westphalia", "New South Wales"}:
        return "metro", 1, 2, 1, False, serviceable
    return "standard", 2, 3, 2, False, serviceable


def select_warehouses(country: str, region: str) -> list[tuple[str, str, str]]:
    country_warehouses = WAREHOUSES[country]
    primary = next((item for item in country_warehouses if item[2] == region), country_warehouses[0])
    secondary = next((item for item in country_warehouses if item != primary), country_warehouses[0])
    return [primary, secondary]


def generate_rows(postal_codes_per_city: int, as_of_date: date) -> dict[str, list[dict[str, object]]]:
    location_rows: list[dict[str, object]] = []
    delivery_rows: list[dict[str, object]] = []
    warehouse_rows: list[dict[str, object]] = []
    geo_rows_by_key: dict[tuple[str, str, str], dict[str, object]] = {}

    location_number = 1
    for seed in CITY_SEEDS:
        (
            country,
            country_code,
            region,
            region_code,
            subregion,
            state_province,
            city,
            timezone_name,
            market,
            territory,
            postal_seed,
        ) = seed

        geo_rows_by_key[(country, region, subregion)] = {
            "country": country,
            "country_code": country_code,
            "region": region,
            "region_code": region_code,
            "subregion": subregion,
            "market": market,
            "sales_territory": territory,
            "active_flag": True,
            "last_updated_date": as_of_date.isoformat(),
        }

        for offset in range(postal_codes_per_city):
            code = postal_code(country_code, postal_seed, offset)
            delivery_zone, priority, standard_sla, express_sla, remote, serviceable = delivery_profile(
                region, city, location_number
            )
            is_active = location_number % 131 != 0
            effective_to = "" if is_active else as_of_date.isoformat()

            location_rows.append(
                {
                    "location_id": f"loc_{location_number:06d}",
                    "country": country,
                    "region": region,
                    "subregion": subregion,
                    "state_province": state_province,
                    "city": city,
                    "postal_code": code,
                    "timezone": timezone_name,
                    "market_area": market,
                    "is_active": is_active,
                    "effective_from": "2024-01-01",
                    "effective_to": effective_to,
                }
            )

            delivery_rows.append(
                {
                    "postal_code": code,
                    "delivery_zone": delivery_zone,
                    "zone_priority": priority,
                    "standard_sla_days": standard_sla,
                    "express_sla_days": express_sla,
                    "remote_area_flag": remote,
                    "serviceability_flag": serviceable,
                    "last_updated_date": as_of_date.isoformat(),
                }
            )

            warehouses = select_warehouses(country, region)
            primary, secondary = warehouses[0], warehouses[1]
            warehouse_rows.append(
                {
                    "warehouse_id": primary[0],
                    "warehouse_name": primary[1],
                    "warehouse_country": country,
                    "service_region": primary[2],
                    "covered_country": country,
                    "covered_region": region,
                    "covered_postal_code": code,
                    "delivery_type": "standard",
                    "serviceability_flag": serviceable,
                    "max_sla_days": standard_sla,
                    "last_updated_date": as_of_date.isoformat(),
                }
            )
            if serviceable and not remote and location_number % 5 != 0:
                warehouse_rows.append(
                    {
                        "warehouse_id": secondary[0],
                        "warehouse_name": secondary[1],
                        "warehouse_country": country,
                        "service_region": secondary[2],
                        "covered_country": country,
                        "covered_region": region,
                        "covered_postal_code": code,
                        "delivery_type": "express",
                        "serviceability_flag": True,
                        "max_sla_days": express_sla,
                        "last_updated_date": as_of_date.isoformat(),
                    }
                )

            location_number += 1

    return {
        "location_master": location_rows,
        "delivery_zone_lookup": delivery_rows,
        "warehouse_coverage": warehouse_rows,
        "geo_hierarchy": sorted(geo_rows_by_key.values(), key=lambda row: (row["country"], row["region"], row["subregion"])),
    }


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate S3 geography and fulfillment reference CSV files.")
    parser.add_argument("--output-dir", default="datasets/s3_reference", help="Root output folder.")
    parser.add_argument("--postal-codes-per-city", type=int, default=50, help="Rows generated per configured city.")
    parser.add_argument("--as-of-date", default="2026-04-21", help="Reference file last-updated date.")
    args = parser.parse_args()

    if args.postal_codes_per_city <= 0:
        raise ValueError("postal-codes-per-city must be greater than zero")

    as_of_date = date.fromisoformat(args.as_of_date)
    output_root = Path(args.output_dir).expanduser().resolve()
    rows_by_file = generate_rows(args.postal_codes_per_city, as_of_date)

    file_specs = {
        "location_master": (LOCATION_COLUMNS, output_root / "location_master" / "location_master.csv"),
        "delivery_zone_lookup": (DELIVERY_ZONE_COLUMNS, output_root / "delivery_zone_lookup" / "delivery_zone_lookup.csv"),
        "warehouse_coverage": (WAREHOUSE_COVERAGE_COLUMNS, output_root / "warehouse_coverage" / "warehouse_coverage.csv"),
        "geo_hierarchy": (GEO_HIERARCHY_COLUMNS, output_root / "geo_hierarchy" / "geo_hierarchy.csv"),
    }

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of_date": as_of_date.isoformat(),
        "source_role": "aws_s3_geography_fulfillment_reference",
        "files": {},
    }

    for name, (columns, path) in file_specs.items():
        rows = rows_by_file[name]
        write_csv(path, columns, rows)
        manifest["files"][name] = {
            "path": str(path),
            "columns": columns,
            "row_count": len(rows),
        }
        print(f"{name}: {len(rows):,} rows -> {path}")

    manifest_path = output_root / "reference_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
