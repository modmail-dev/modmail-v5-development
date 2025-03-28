"""Provides migration functionality for the MongoDB database.

This module handles database migrations using the Beanie migration system,
allowing for schema evolution and data transformations between versions.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

__all__ = ["do_migration"]


def do_migration(uri: str, db_name: str) -> None:
    """Performs the migration of the MongoDB database.

    Executes all pending migrations for the specified database using Beanie's
    migration system. Migrations are loaded from the local migrations directory.

    Args:
        uri: The MongoDB connection URI string.
        db_name: The name of the database to migrate.
    """
    # Keep this import here to avoid logging issues.
    from beanie.executors import migrate
    from beanie.migrations.models import RunningDirections

    path = Path(__file__).absolute().parent / "migrations"
    settings = migrate.MigrationSettings(
        distance=0,  # Run all migrations
        direction=RunningDirections.FORWARD,
        connection_uri=uri,
        database_name=db_name,
        path=path,
        allow_index_dropping=True,
        use_transaction=True,
    )
    asyncio.run(migrate.run_migrate(settings))
