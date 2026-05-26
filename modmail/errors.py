"""Custom exceptions used throughout Modmail."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from discord.ext import commands

if TYPE_CHECKING:
    import datetime

    import discord

    from .core.context import UserAccessResult

__all__ = [
    "BadPermissionsError",
    "CacheNotReadyError",
    "ConfigUpdateError",
    "DatabaseConnectionError",
    "DatabaseError",
    "DatabaseOperationError",
    "InstanceAlreadyRunningError",
    "LocalizedBadArgumentError",
    "ModmailError",
    "NoModmailCategoryError",
    "NoStaffGuildError",
    "NoTicketChannelError",
    "NotInTicketError",
    "StaffGuildNotConfiguredError",
    "TicketCreationError",
    "TicketNotFoundError",
    "UserAccessError",
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


class CacheNotReadyError(DatabaseError):
    """Exception raised when a cached property is accessed before the cache is populated.

    Raised by [DBClient][modmail.backends.common.db_client.DBClient] when any cached
    property or cache-dependent method is called before [`connect`][] has completed its
    initial sync. Await [`wait_until_ready`][] if you need to block until the cache is
    available.
    """


class DatabaseConnectionError(DatabaseError):
    """Exception for database connection errors.

    Raised when the application fails to establish a connection with the database.
    """


class DatabaseOperationError(DatabaseError):
    """Exception raised when a database read or write operation fails unexpectedly.

    Raised by persistence operations when an unexpected database error occurs
    that is not a connection or locking issue (e.g. a query failure, serialization
    error, or unexpected driver exception).
    """


class InstanceAlreadyRunningError(DatabaseConnectionError):
    """Exception raised when another instance of the bot is already running.

    Raised during startup if the instance lock in the database is held by an active process.

    """

    def __init__(self, hostname: str | None, pid: int | None, acquired_at: datetime.datetime | None) -> None:
        """Initialize the error.

        Args:
            hostname: The hostname of the running instance.
            pid: The process ID of the running instance.
            acquired_at: When the running instance acquired the lock, or None if unknown.
        """
        self.hostname = hostname
        """The hostname of the running instance."""
        self.pid = pid
        """The process ID of the running instance."""
        self.acquired_at = acquired_at
        """When the instance lock was acquired."""
        super().__init__()


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


class BadPermissionsError(ModmailError, commands.CheckFailure):
    """Exception raised when the bot lacks permissions required to complete an operation."""

    def __init__(
        self,
        *,
        channel: discord.abc.Messageable | discord.abc.GuildChannel | discord.Guild | None,
        missing: discord.Permissions | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            channel: The channel or guild in which the permission check failed.
            missing: Permissions that are required but not held.
        """
        self.channel = channel
        """The channel or guild in which the permission check failed."""
        self.missing = missing
        """Permissions that are missing."""
        parts: list[str] = []
        if channel is not None:
            parts.append(f"in {channel!r}")
        if missing is not None:
            names = [name for name, val in missing if val]
            parts.append(f"missing: {', '.join(names)}")
        message = "Bot lacks required permissions" + (f" ({'; '.join(parts)})" if parts else "") + "."
        super().__init__(message)


class TicketCreationError(ModmailError):
    """Exceptions during ticket creation.

    Raised when an operation attempts to create a ticket but fails due to various reasons.
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


class LocalizedBadArgumentError(ModmailError, commands.BadArgument):
    """A [`commands.BadArgument`][] that carries a [`locale_str`][] key.

    Raised by converters and transformers when an argument cannot be resolved.
    [`Bot.on_command_error`][modmail.core.bot.Bot.on_command_error] translates
    [`locale_key`][] into the invoking user's locale before sending the reply.

    """

    def __init__(self, key: discord.app_commands.locale_str) -> None:
        """Initialize with a locale key.

        Args:
            key: The Fluent message key for the translated error message.
        """
        self.locale_key = key
        """The locale key for the error message."""
        super().__init__(str(key))


class UserAccessError(ModmailError, commands.CheckFailure):
    """Raised when a user is denied access to a command.

    Wraps the full [`UserAccessResult`][] so callers have structured access
    to the denial reason without inspecting the context.

    """

    def __init__(self, result: UserAccessResult) -> None:
        """Initialize with the denial result.

        Args:
            result: The [`UserAccessResult`][] with `allowed=False`.
        """
        self.result = result
        """The access check result."""
        super().__init__(str(result))


class ConfigUpdateError(ModmailError):
    """Raised when a config update fails validation or parsing.

    Attributes:
        reason: Short category label for the failure type. Use in the
            command handler to select a vague user-facing message.
        detail: Full detail message for logging (not user-facing).
    """

    def __init__(self, reason: Literal["parse", "validation", "internal", "readonly"], detail: str = "") -> None:
        """Initialize with a reason category and optional log detail.

        Args:
            reason: One of `"parse"`, `"validation"`, `"internal"`, `"readonly"`.
            detail: Full description of the failure (logged, not shown to users).
        """
        self.reason = reason
        """Short category label for the failure type."""
        self.detail = detail
        """Full detail message for logging (not user-facing)."""
        super().__init__(reason)
