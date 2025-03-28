"""
modmail.errors
==============
This module defines custom exceptions used throughout the Modmail project.
"""

from __future__ import annotations

__all__ = [
    "DatabaseConnectionError",
    "DatabaseError",
    "ModmailError",
]


class ModmailError(Exception):
    """Base class for all Modmail-related errors."""

    pass


class DatabaseError(ModmailError):
    """Base class for all database-related errors."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Custom exception for database connection errors."""

    pass
