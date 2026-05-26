"""Database backend factory.

This module provides the `create_db_client` factory function which selects
and instantiates the appropriate backend based on the bot configuration,
returning a fully wired DBClient ready for `connect()` to be called.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .common.db_client import DBClient
from .common.models import (
    ActivityModel,
    InstanceLockModel,
    ProfileModel,
    SettingsModel,
    TicketDMMessageModel,
    TicketMessageModel,
    TicketModel,
    TicketUserModel,
)

if TYPE_CHECKING:
    from ..config.models import Config


__all__ = [
    "ActivityModel",
    "DBClient",
    "InstanceLockModel",
    "ProfileModel",
    "SettingsModel",
    "TicketDMMessageModel",
    "TicketMessageModel",
    "TicketModel",
    "TicketUserModel",
    "create_db_client",
]


def create_db_client(config: Config) -> DBClient:
    """Create and return a DBClient wired to the correct backend.

    Imports are deferred to the body of this function so that backend-specific
    optional dependencies (SQLAlchemy, beanie, etc.) are only imported if the
    corresponding backend is actually selected.

    Args:
        config: The bot configuration object.  The `database.backend_type` field
            determines which backend implementation is instantiated.

    Returns:
        A DBClient wrapping the appropriate backend, ready for `connect()`
        to be called.

    Raises:
        ValueError: If `config.database.backend_type` is not a recognized backend name.
    """
    backend_type = config.database.backend_type
    if backend_type == "sql":
        from .sql.backend import SQLBackend

        return DBClient(SQLBackend(config))

    if backend_type == "mongodb":
        from .mongodb.backend import MongoDBBackend

        return DBClient(MongoDBBackend(config))

    raise ValueError(f"Unknown database type: {backend_type!r}")
