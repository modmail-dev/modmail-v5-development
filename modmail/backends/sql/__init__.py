"""SQL database backend implementation.

This module provides SQL database backend functionality for the Modmail bot,
including the client for database interaction.
"""

from __future__ import annotations

from .client import SQLClient

__all__ = [
    "SQLClient",
]
