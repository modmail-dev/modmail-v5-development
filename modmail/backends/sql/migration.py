"""
modmail.backends.sql.migration
==============================
This module handles the migration of the SQL database using Alembic.
"""

from __future__ import annotations

import os

__all__ = ["do_migration"]


def do_migration(uri: str) -> None:
    """
    Performs the migration of the SQL database using Alembic.

    :param uri: The SQL database connection URI.
    """
    from alembic import command
    from alembic.config import Config

    # Determine the absolute path to the .ini file.
    ini_location = os.path.join(os.path.abspath(os.path.dirname(__file__)), "migrations", "alembic.ini")

    # Create an Alembic configuration instance.
    alembic_cfg = Config(file_=ini_location)

    # Set the database URI for Alembic. The URI should include the database name,
    # but if the URI requires dynamic construction with db_name, adjust here.
    alembic_cfg.set_main_option("sqlalchemy.url", uri)

    # Run the migrations: upgrade to the latest revision.
    command.upgrade(alembic_cfg, "head")
