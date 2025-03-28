"""Custom exceptions used throughout the Modmail project.

This module defines a hierarchy of custom exceptions that are used for
error handling and reporting within the Modmail application.
"""

from __future__ import annotations

__all__ = [
    "DatabaseConnectionError",
    "DatabaseError",
    "ModmailError",
]


class ModmailError(Exception):
    """Base class for all Modmail-related errors.

    All custom exceptions in the Modmail application should inherit from this class
    to allow for generic error catching.
    """


class DatabaseError(ModmailError):
    """Base class for all database-related errors.

    Used for errors that occur during database operations, excluding connection issues.
    """


class DatabaseConnectionError(DatabaseError):
    """Exception for database connection errors.

    Raised when the application fails to establish a connection with the database.
    """
