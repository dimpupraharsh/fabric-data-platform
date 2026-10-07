"""Read the live Warehouse schema into reviewed, idempotent bootstrap migrations.

Only catalog metadata is exported. No runtime states, watermarks, customer rows,
sales rows, source credentials, or operational logs are selected.
"""

import argparse
import re
import struct
from pathlib import Path

import pyodbc

from fabric_api import FabricAPI

ROOT = Path(__file__).resolve().parents[1]


def quote(name):
    """Quote SQL identifiers using the SQL Server/Fabric bracket convention."""
    return "[" + name.replace("]", "]]") + "]"


def connect(api, workspace_id, warehouse_id):
    """Discover the target SQL endpoint; authenticate without a saved password."""
    item = api.call("GET", f"workspaces/{workspace_id}/warehouses/{warehouse_id}")
    server = item["properties"]["connectionString"]
    token = api.credential.get_token("https://database.windows.net/.default").token.encode("utf-16-le")
    return pyodbc.connect(
        f"Driver={{ODBC Driver 18 for SQL Server}};Server={server};Database={item['displayName']};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30",
        attrs_before={1256: struct.pack("<I", len(token)) + token}, autocommit=True,
    )


def export(connection):
    """Return CREATE-if-missing tables followed by CREATE OR ALTER modules."""
    rows = connection.execute("""
      SELECT s.name,t.name,c.name,ty.name,c.max_length,c.precision,c.scale,
             c.is_nullable,c.is_identity,c.is_computed,c.column_id
      FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id
      JOIN sys.columns c ON t.object_id=c.object_id
      JOIN sys.types ty ON c.user_type_id=ty.user_type_id
      WHERE s.name IN ('control','gold') ORDER BY s.name,t.name,c.column_id
    """).fetchall()
    tables = {}
    schemas = set()
    for schema, table, column, typ, size, precision, scale, nullable, identity, computed, _ in rows:
        if computed:
            raise RuntimeError("Computed columns require an explicitly reviewed migration")
        schemas.add(schema)
        datatype = typ
        if typ in ("varchar", "char", "varbinary", "binary", "nvarchar", "nchar"):
            width = "max" if size == -1 else str(size // 2 if typ.startswith("n") else size)
            datatype += f"({width})"
        elif typ in ("decimal", "numeric"):
            datatype += f"({precision},{scale})"
        elif typ in ("datetime2", "datetimeoffset", "time"):
            datatype += f"({scale})"
        definition = f"    {quote(column)} {datatype}"
        if identity:
            definition += " IDENTITY"
        definition += " NULL" if nullable else " NOT NULL"
        tables.setdefault((schema, table), []).append(definition)
    statements = ["-- Catalog-only export. Creates missing objects; never drops data or resets state."]
    for schema in sorted(schemas):
        statements.append(f"IF SCHEMA_ID('{schema}') IS NULL EXEC('CREATE SCHEMA {quote(schema)}');\nGO")
    for (schema, table), columns in tables.items():
        statements.append(f"IF OBJECT_ID('{schema}.{table}', 'U') IS NULL\nBEGIN\n"
                          f"  CREATE TABLE {quote(schema)}.{quote(table)} (\n" + ",\n".join(columns) + "\n  );\nEND;\nGO")
    modules = connection.execute("""
      SELECT s.name,o.name,m.definition FROM sys.sql_modules m
      JOIN sys.objects o ON m.object_id=o.object_id
      JOIN sys.schemas s ON s.schema_id=o.schema_id
      WHERE s.name IN ('control','gold') AND o.type IN ('P','V')
      ORDER BY CASE WHEN o.type='V' THEN 1 ELSE 2 END,o.name
    """).fetchall()
    for schema, name, definition in modules:
        if definition is None:
            raise RuntimeError(f"Missing module definition {schema}.{name}")
        definition = re.sub(r"\bCREATE\s+(?:OR\s+ALTER\s+)?(PROCEDURE|PROC|VIEW)\b",
                            r"CREATE OR ALTER \1", definition, count=1, flags=re.I)
        statements.append(definition.strip() + "\nGO")
    return "\n\n".join(statements) + "\n", len(tables), len(modules)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--name", choices=["wh_retail_control", "wh_retail_gold"], required=True)
    args = parser.parse_args()
    api = FabricAPI()
    with connect(api, args.workspace_id, args.warehouse_id) as connection:
        sql, tables, modules = export(connection)
    path = ROOT / "migrations" / args.name / "V001__baseline_schema.sql"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sql)
    print(f"Exported catalog: {args.name}, {tables} tables, {modules} modules")


if __name__ == "__main__":
    main()
