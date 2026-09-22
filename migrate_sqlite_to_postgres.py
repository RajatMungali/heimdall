"""
migrate_sqlite_to_postgres.py
Copies all rows from SQLite databases into the PostgreSQL Docker container.

Usage:
    uv run python migrate_sqlite_to_postgres.py
"""
import sqlite3
import json
import psycopg2

# -- Connection settings
SQLITE_DBS = [
    "lead_intelligence.db",
    "backend/lead_intelligence.db",
    "backend/heimdall.db",
    "heimdall_dev.db",
]
PG_DSN = "postgresql://postgres:postgrespassword@localhost:5432/lead_intelligence"

# -- Tables in correct dependency order (parent before child)
TABLES = [
    "pipeline_status",
    "scrape_ledger",
    "lead_snapshots",
    "social_posts",
    "scrape_cache",
    "ats_job_runs",
    "ats_job_snapshots",
    "deleted_ats_jobs",
]


def coerce(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def migrate_table(sqlite_cur, pg_cur, table: str) -> int:
    try:
        sqlite_cur.execute(f'SELECT * FROM "{table}"')
    except sqlite3.OperationalError:
        return 0

    rows = sqlite_cur.fetchall()
    if not rows:
        return 0

    col_names = [d[0] for d in sqlite_cur.description]
    col_str = ", ".join(f'"{c}"' for c in col_names)
    placeholders = ", ".join(["%s"] * len(col_names))

    inserted = 0
    for row in rows:
        values = tuple(coerce(v) for v in row)
        try:
            pg_cur.execute(
                f"INSERT INTO {table} ({col_str}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING",
                values,
            )
            inserted += pg_cur.rowcount
        except Exception as e:
            print(f"    [SKIP] Row skipped in {table}: {e}")
    return inserted


def main():
    print("=" * 60)
    print("SQLite -> PostgreSQL Data Migration")
    print("=" * 60)

    try:
        pg_conn = psycopg2.connect(PG_DSN)
        pg_conn.autocommit = False
        pg_cur = pg_conn.cursor()
        print(f"[OK] Connected to PostgreSQL: {PG_DSN.split('@')[1]}\n")
    except Exception as e:
        print(f"[ERROR] Failed to connect to PostgreSQL: {e}")
        return

    total_migrated = 0

    for db_path in SQLITE_DBS:
        try:
            sqlite_conn = sqlite3.connect(db_path)
            sqlite_conn.row_factory = sqlite3.Row
            sqlite_cur = sqlite_conn.cursor()

            existing = {
                r[0]
                for r in sqlite_cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            overlap = existing & set(TABLES)
            if not overlap:
                sqlite_conn.close()
                continue

            print(f"[DB] Processing: {db_path}")
            print(f"     Tables found: {overlap}")

            db_total = 0
            for table in TABLES:
                if table not in existing:
                    continue
                count = migrate_table(sqlite_cur, pg_cur, table)
                if count > 0:
                    print(f"    [INSERTED] {table}: {count} rows")
                    db_total += count
                else:
                    rc = sqlite_cur.execute(
                        f'SELECT COUNT(*) FROM "{table}"'
                    ).fetchone()[0]
                    if rc > 0:
                        print(f"    [SKIPPED]  {table}: {rc} rows already in Postgres")

            pg_conn.commit()
            print(f"  [COMMIT] {db_total} rows committed from {db_path}\n")
            total_migrated += db_total
            sqlite_conn.close()

        except Exception as e:
            print(f"  [ERROR] {db_path}: {e}")
            pg_conn.rollback()

    pg_cur.close()
    pg_conn.close()

    print("=" * 60)
    print(f"Migration complete! Total rows migrated: {total_migrated}")
    print("=" * 60)


if __name__ == "__main__":
    main()
