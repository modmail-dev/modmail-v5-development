"""SQL database migration handling using Alembic.

This module handles the migration of the SQL database using Alembic.

To create a new migration, use the following command:
    alembic -c modmail/backends/sql/migrations/alembic.ini revision --autogenerate -m "migration_name"

Note:
    Must set database_type to sql and supply connection uri in configs first.
    Then manually edit the migration file to add the necessary changes.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["do_migration"]


def do_migration(uri: str) -> None:
    """Perform SQL database migration using Alembic.

    Args:
        uri: The SQL database connection URI.
    """
    from alembic import command
    from alembic.config import Config

    # Determine the absolute path to the .ini file.
    ini_location = Path(__file__).absolute().parent / "migrations" / "alembic.ini"

    # Create an Alembic configuration instance.
    alembic_cfg = Config(file_=ini_location)

    # Set the database URI for Alembic. The URI should include the database name,
    # but if the URI requires dynamic construction with db_name, adjust here.
    alembic_cfg.set_main_option("sqlalchemy.url", uri)

    # Run the migrations: upgrade to the latest revision.
    command.upgrade(alembic_cfg, "head")
