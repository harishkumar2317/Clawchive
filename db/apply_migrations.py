"""Apply raw SQL migrations in filename order.

Requires either the ``psycopg`` (v3) or ``psycopg2`` PostgreSQL driver.
"""

import os
import sys
from pathlib import Path
from typing import Any


MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_connection(database_url: str) -> Any:
    """Return a PostgreSQL connection using an installed supported driver."""
    try:
        import psycopg

        return psycopg.connect(database_url)
    except ImportError:
        try:
            import psycopg2
        except ImportError as error:
            raise RuntimeError(
                "Install a PostgreSQL driver first: pip install 'psycopg[binary]'"
            ) from error
        return psycopg2.connect(database_url)


def get_migration_files() -> list[Path]:
    """Return SQL migration files ordered by filename."""
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def apply_migrations(database_url: str) -> None:
    """Apply each migration not already listed in schema_migrations."""
    with get_connection(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

        for migration_path in get_migration_files():
            migration_name = migration_path.name
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM schema_migrations WHERE filename = %s",
                    (migration_name,),
                )
                if cursor.fetchone() is not None:
                    print(f"Skipping {migration_name} (already applied)")
                    continue

                print(f"Applying {migration_name}")
                cursor.execute(migration_path.read_text(encoding="utf-8"))
                cursor.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (migration_name,),
                )


def main() -> int:
    """Apply migrations using DATABASE_URL and return a process exit code."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL must be set.", file=sys.stderr)
        return 1

    try:
        apply_migrations(database_url)
    except Exception as error:
        print(f"Migration failed: {error}", file=sys.stderr)
        return 1

    print("Migrations complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
