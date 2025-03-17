"""
modmail.backends.mongodb.migration
==================================
This module handles the migration of the MongoDB database using Beanie.

To create a new migration, use the following command:
    beanie new-migration -n migration_name -p modmail/backends/mongodb/migrations
Then manually edit the migration file to add the necessary changes.
See: https://beanie-odm.dev/tutorial/migrations/.
"""

from __future__ import annotations

import asyncio
import os

__all__ = ["do_migration"]


def do_migration(uri: str, db_name: str) -> None:
    """
    Performs the migration of the database.
    This function should be called outside the main event loop.

    :param uri: The MongoDB connection URI.
    :param db_name: The name of the database to migrate.
    """
    # Keep this import here to avoid logging issues.
    from beanie.executors import migrate
    from beanie.migrations.models import RunningDirections

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
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
