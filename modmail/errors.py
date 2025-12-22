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
    "NoTicketChannelError",
    "NotInTicketError",
    "StaffGuildNotConfiguredError",
    "TicketCreationError",
    "TicketNotFoundError",
    "TicketRecipientOccupiedError",
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
    """Exception for when the Modmail category or forum is not found.

    Raised when an operation requires the Modmail category or forum but none is found.
    """


class NoTicketChannelError(ModmailError):
    """Exception for when the ticket channel is not found.

    Raised when an operation requires a ticket channel but none is found.
    """


class BadPermissionsError(ModmailError):
    """Exception for when the bot lacks necessary permissions.

    Raised when an operation requires certain permissions but the bot does not have them.
    """


class TicketCreationError(ModmailError):
    """Exceptions during ticket creation.

    Raised when an operation attempts to create a ticket but fails due to various reasons.
    """


class TicketRecipientOccupiedError(TicketCreationError):
    """Exception for when the recipient is already in another open ticket.

    Raised when an operation attempts to create a ticket with an occupied recipient.
    """


class TicketNotFoundError(ModmailError):
    """Exception for when a ticket is not found.

    Raised when an operation requires a ticket, but it cannot be found in the database.
    """


class NotInTicketError(ModmailError, commands.CheckFailure):
    """Exception for when a user is not in a ticket.

    Raised when an operation requires the user to be in a ticket, but they are not.
    """


class StaffGuildNotConfiguredError(ModmailError, commands.CheckFailure):
    """Exception for when the staff guild is not configured.

    Raised when an operation requires the staff guild to be configured, but it is not.
    """
