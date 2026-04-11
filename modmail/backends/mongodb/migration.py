"""MongoDB migration runner using the Beanie migration system."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

__all__ = ["do_migration"]


def _run_migration(uri: str, db_name: str) -> None:
    """Run all pending Beanie migrations synchronously.

    Intended to be called from a worker process (via [`do_migration`][]) that
    has no running event loop, so [`asyncio.run`][] can start a fresh one.

    Args:
        uri: The MongoDB connection URI.
        db_name: Name of the database to migrate.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s: %(message)s")

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


async def do_migration(uri: str, db_name: str) -> None:
    """Run all pending Beanie migrations against the given database.

    Delegates to a worker process so the event loop is not blocked, and so
    that the internal [`asyncio.run`][] call gets a loop-free process in
    which to start its own event loop.

    Args:
        uri: The MongoDB connection URI.
        db_name: Name of the database to migrate.
    """
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor() as pool:
        await loop.run_in_executor(pool, _run_migration, uri, db_name)
