"""Custom exceptions used throughout the Modmail project.

This module defines a hierarchy of custom exceptions that are used for
error handling and reporting within the Modmail application.
"""

from __future__ import annotations

from discord.ext import commands

__all__ = [
    "BadPermissionsError",
    "DatabaseConnectionError",
    "DatabaseError",
    "ModmailError",
    "NoModmailCategoryError",
    "NoStaffGuildError",
    "NoThreadChannelError",
    "NotInThreadError",
    "StaffGuildNotConfiguredError",
    "ThreadCreationError",
    "ThreadNotFoundError",
    "ThreadRecipientOccupiedError",
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


class NoStaffGuildError(ModmailError):
    """Exception for when the staff guild is not set.

    Raised when an operation requires a staff guild but none has been set.
    """


class NoModmailCategoryError(ModmailError):
    """Exception for when the Modmail category is not found.

    Raised when an operation requires the Modmail category but none is found.
    """


class NoThreadChannelError(ModmailError):
    """Exception for when the thread channel is not found.

    Raised when an operation requires a thread channel but none is found.
    """


class BadPermissionsError(ModmailError):
    """Exception for when the bot lacks necessary permissions.

    Raised when an operation requires certain permissions but the bot does not have them.
    """


class ThreadCreationError(ModmailError):
    """Exceptions during thread creation.

    Raised when an operation attempts to create a thread but fails due to various reasons.
    """


class ThreadRecipientOccupiedError(ThreadCreationError):
    """Exception for when the recipient is already in another open thread.

    Raised when an operation attempts to create a thread with an occupied recipient.
    """


class ThreadNotFoundError(ModmailError):
    """Exception for when a thread is not found.

    Raised when an operation requires a thread but it cannot be found in the database.
    """


class NotInThreadError(ModmailError, commands.CheckFailure):
    """Exception for when a user is not in a thread.

    Raised when an operation requires the user to be in a thread, but they are not.
    """


class StaffGuildNotConfiguredError(ModmailError, commands.CheckFailure):
    """Exception for when the staff guild is not configured.

    Raised when an operation requires the staff guild to be configured, but it is not.
    """
