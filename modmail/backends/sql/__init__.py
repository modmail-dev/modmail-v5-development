"""SQL database backend implementation.

This module provides SQL database backend functionality for the Modmail bot,
including the client for database interaction.
"""

from __future__ import annotations

from .client import SQLClient

try:
    import aiosqlite  # ensure aiosqlite is installed for static analysis tools

    del aiosqlite
except ImportError:
    raise ImportError(
        "The 'aiosqlite' package is required for the SQL backend. "
        "Please install it with 'pip install sqlalchemy[asyncio,aiosqlite]'."
    ) from None

__all__ = [
    "SQLClient",
]
