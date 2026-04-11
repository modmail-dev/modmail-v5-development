"""Generate a new Alembic migration against a temporary SQLite database.

Creates a temp SQLite database, upgrades it to head so Alembic can diff the
current ORM state against it, runs autogenerate, then deletes the temp file.

The generated migration files use SQLAlchemy abstract types and work on all
supported dialects (SQLite, PostgreSQL, MySQL/MariaDB).  The one exception is
PostgreSQL native enum type management (``CREATE TYPE`` / ``DROP TYPE``):
autogenerate cannot emit those from a SQLite diff, so add them manually if a
migration adds or removes an enum column.

Usage:
    uv run python scripts/make_migration.py -m "description of change"
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    """Parse args and run the autogenerate workflow."""
    parser = argparse.ArgumentParser(description="Auto-generate an Alembic migration.")
    parser.add_argument("-m", "--message", required=True, help="Migration message (used in the filename).")
    args = parser.parse_args()

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        url = f"sqlite+aiosqlite:///{tmp_path}"
        env = {**os.environ, "ALEMBIC_URL": url}

        # Upgrade to head first so autogenerate diffs against the full current
        # schema rather than an empty database.
        result = subprocess.run(["uv", "run", "alembic", "upgrade", "head"], env=env, check=False)
        if result.returncode != 0:
            sys.exit(result.returncode)

        result = subprocess.run(
            ["uv", "run", "alembic", "revision", "--autogenerate", "-m", args.message],
            env=env,
            check=False,
        )
        sys.exit(result.returncode)
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
