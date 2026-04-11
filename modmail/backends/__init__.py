"""Database backend factory.

This module provides the ``create_db_client`` factory function which selects
and instantiates the appropriate backend based on the bot configuration,
returning a fully wired DBClient ready for ``connect()`` to be called.

Notes:
    Modules from this directory should not import from ``modmail.core.*``
    to avoid circular import issues.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .common.db_client import DBClient

if TYPE_CHECKING:
    from modmail.config.models import Config


__all__ = ["create_db_client"]


def create_db_client(config: Config) -> DBClient:
    """Create and return a DBClient wired to the correct backend.

    Imports are deferred to the body of this function so that backend-specific
    optional dependencies (SQLAlchemy, beanie, etc.) are only imported if the
    corresponding backend is actually selected.

    Args:
        config: The bot configuration object.  The ``database_type`` field
            determines which backend implementation is instantiated.

    Returns:
        A DBClient wrapping the appropriate backend, ready for ``connect()``
        to be called.

    Raises:
        ValueError: If ``config.database_type`` is not a recognized backend name.
    """
    if config.database_type == "sql":
        from .sql.backend import SQLBackend

        return DBClient(SQLBackend(config))

    if config.database_type == "mongodb":
        from .mongodb.backend import MongoDBBackend

        return DBClient(MongoDBBackend(config))

    raise ValueError(f"Unknown database type: {config.database_type!r}")
