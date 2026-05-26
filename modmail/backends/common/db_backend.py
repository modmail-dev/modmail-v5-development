"""Abstract base class for database backends.

Defines the interface that all database backend implementations must fulfill, plus
the shared instance-lock mechanism that prevents two processes from running
the same bot simultaneously.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import logging
import os
import socket
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, overload

from modmail.errors import DatabaseOperationError, InstanceAlreadyRunningError

from .models import InstanceLockModel

if TYPE_CHECKING:
    from modmail.config.models import Config, DatabaseConfig
    from modmail.enum import TicketStatus

    # Resolve docs import
    from modmail.errors import (
        DatabaseConnectionError,  # pyright: ignore [reportUnusedImport]  # noqa: F401
        TicketCreationError,  # pyright: ignore [reportUnusedImport]  # noqa: F401
        TicketNotFoundError,  # pyright: ignore [reportUnusedImport]  # noqa: F401
    )

    # Resolve docs import
    from .db_client import DBClient  # pyright: ignore [reportUnusedImport]  # noqa: F401
    from .models import ProfileModel, SettingsModel, TicketMessageModel, TicketModel, TicketUserModel

__all__ = ["DBBackend", "LockInfo"]

logger = logging.getLogger(__name__)

_LOCK_HEARTBEAT_INTERVAL: int = 5
_LOCK_STALE_THRESHOLD: int = 20


@dataclass
class LockInfo:
    """Information about the current instance lock holder."""

    hostname: str
    """Network hostname of the machine holding the lock."""
    pid: int
    """OS process ID of the lock holder on [`hostname`][]."""
    acquired_at: datetime.datetime | None
    """UTC-aware timestamp when the lock was first acquired (`None` if unavailable)."""
    heartbeat_at: datetime.datetime
    """Most recent heartbeat timestamp, used to detect stale locks."""


class DBBackend(ABC):
    """Abstract base for database backends.

    Declares the persistence primitives that each concrete backend must implement.
    Also provides the shared instance-lock mechanism to prevent two processes from
    running the same bot simultaneously.

    Note:
        **Do not add caching in the backend.** All caching is managed by [DBClient][]{ data-preview }.

        Catch database-specific errors in the implementation and re-raise them as
        [DatabaseOperationError][]{ data-preview } for unexpected failures.
    """

    def __init__(self, config: Config) -> None:
        """Initialize the backend.

        Args:
            config: The bot [Config][]{ data-preview }.
        """
        self._config = config
        self._instance_id: str = str(uuid.uuid4())
        self._heartbeat_task: asyncio.Task[None] | None = None

    @property
    def _db_config(self) -> DatabaseConfig:
        """The [DatabaseConfig][]{ data-preview } for this `bot_id`."""
        return self._config.database

    @abstractmethod
    async def _try_insert_lock(self, lock_data: InstanceLockModel) -> bool:
        """Attempt to insert a new lock for this `bot_id`.

        The lock record must be uniquely constrained on `bot_id` so
        concurrent inserts fail.

        Args:
            lock_data: The [InstanceLockModel][]{ data-preview } to insert.

        Returns:
            True: If insert succeeded.
            False: If another instance already holds the lock.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def _read_lock(self) -> LockInfo | None:
        """Read the current lock holder for this `bot_id`.

        Returns:
            LockInfo: If a lock exists.
            None: If no lock is present.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def _try_takeover_lock(self, stale_cutoff: datetime.datetime, lock_data: InstanceLockModel) -> bool:
        """Atomically overwrite the lock only when `heartbeat_at` <= `stale_cutoff`.

        Args:
            stale_cutoff: UTC-aware datetime threshold.
            lock_data: New [InstanceLockModel][]{ data-preview } to write on success.

        Returns:
            True: If the update succeeded (this instance now owns the lock).
            False: If the lock was not stale or was already taken over by another process.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def _delete_lock(self) -> None:
        """Delete this instance's lock.

        Must be a no-op when the lock does not exist.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def _update_heartbeat(self) -> bool:
        """Update `heartbeat_at` for this instance's lock.

        Returns:
            True: If the lock still belongs to this instance.
            False: If the lock no longer belongs to this instance.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    def _build_lock_data(self, now: datetime.datetime) -> InstanceLockModel:
        """Build an [InstanceLockModel][]{ data-preview } for the given timestamp.

        Args:
            now: UTC-aware datetime to use for `acquired_at` and `heartbeat_at`.

        Returns:
            InstanceLockModel: Ready to pass to [`_try_insert_lock`][] or [`_try_takeover_lock`][].
        """
        return InstanceLockModel(
            bot_id=self._config.bot.bot_id,
            instance_id=self._instance_id,
            acquired_at=now,
            heartbeat_at=now,
            hostname=socket.gethostname(),
            pid=os.getpid(),
        )

    async def _acquire_instance_lock(self) -> None:
        """Acquire the instance lock for this `bot_id` in the database.

        Raises:
            InstanceAlreadyRunningError: If another live instance is already running.
            DatabaseOperationError: If an unexpected database error occurs during lock acquisition.
        """
        now = datetime.datetime.now(datetime.UTC)
        lock_data = self._build_lock_data(now)

        if await self._try_insert_lock(lock_data):
            logger.debug("Acquired instance lock (new).")
            return

        stale_cutoff = now - datetime.timedelta(seconds=_LOCK_STALE_THRESHOLD)
        existing = await self._read_lock()

        if existing is None:
            raise InstanceAlreadyRunningError(None, None, None)

        logger.debug(
            "Existing lock heartbeat_at=%s, stale_cutoff=%s (threshold=%ds), is_stale=%s",
            existing.heartbeat_at,
            stale_cutoff,
            _LOCK_STALE_THRESHOLD,
            existing.heartbeat_at <= stale_cutoff,
        )

        if existing.heartbeat_at > stale_cutoff:
            raise InstanceAlreadyRunningError(existing.hostname, existing.pid, existing.acquired_at)

        if not await self._try_takeover_lock(stale_cutoff, lock_data):
            try:
                winner = await self._read_lock()
            except DatabaseOperationError:
                winner = None
            raise InstanceAlreadyRunningError(
                winner.hostname if winner else None,
                winner.pid if winner else None,
                winner.acquired_at if winner else None,
            )

        logger.warning(
            "Previous instance lock was stale (last heartbeat: %s, host: %s, PID: %d). "
            "Took over the lock. If that instance is still running, conflicts may occur.",
            existing.heartbeat_at,
            existing.hostname,
            existing.pid,
        )

    async def _heartbeat_loop(self) -> None:
        """Continuously refresh the instance lock heartbeat while the bot runs."""
        consecutive_failures = 0
        while True:
            await asyncio.sleep(_LOCK_HEARTBEAT_INTERVAL)
            try:
                success = await self._update_heartbeat()
                consecutive_failures = 0
                if not success:
                    logger.critical(
                        "Instance lock was lost unexpectedly (heartbeat UPDATE failed). "
                        "The database may have been modified externally."
                    )
            except Exception:
                consecutive_failures += 1
                logger.warning(
                    "Failed to update instance lock heartbeat (consecutive failures: %d).",
                    consecutive_failures,
                    exc_info=True,
                )

    async def _release_instance_lock(self) -> None:
        """Cancel the heartbeat task and delete this instance's lock.

        Note:
            Safe to call even if the lock was never acquired.
        """
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None

        try:
            await self._delete_lock()
        except DatabaseOperationError:
            logger.debug("Failed to delete instance lock (DB may already be closed).", exc_info=True)
            return
        logger.debug("Released instance lock.")

    @abstractmethod
    async def _connect(self) -> None:
        """Connect to the database and perform startup procedures.

        Note:
            Implementation must call [`_acquire_instance_lock`][]{ data-preview }
            immediately after connecting, before doing any other work.

        Raises:
            DatabaseConnectionError: If the connection attempt fails.
            InstanceAlreadyRunningError: If another live instance is already running.
        """

    async def connect(self) -> None:
        """Connect to the database and start the heartbeat task.

        Raises:
            DatabaseConnectionError: If the connection attempt fails.
            InstanceAlreadyRunningError: If another live instance is already running.
        """
        try:
            await self._connect()
        except Exception:
            with contextlib.suppress(Exception):
                await self._disconnect()
            raise
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="instance-lock-heartbeat")

    @abstractmethod
    async def _disconnect(self) -> None:
        """Close the database connection."""

    async def disconnect(self) -> None:
        """Release the instance lock and close the database connection."""
        try:
            await self._release_instance_lock()
        finally:
            await self._disconnect()

    @abstractmethod
    async def fetch_settings(self) -> SettingsModel:
        """Load the current settings, creating a default row if none exists yet.

        Returns:
            SettingsModel: The current [SettingsModel][]{ data-preview } for this `bot_id`.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def persist_settings(self, model: SettingsModel) -> None:
        """Upsert a [SettingsModel][]{ data-preview } to the database.

        Creates the settings if it does not yet exist, otherwise updates it in place.

        Args:
            model: The new [SettingsModel][]{ data-preview } to persist.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def fetch_all_profiles(self) -> list[ProfileModel]:
        """Return all [ProfileModel][]{ data-preview } for this `bot_id` from the database.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def persist_profile(self, profile: ProfileModel) -> None:
        """Upsert a [ProfileModel][]{ data-preview } in the database.

        Args:
            profile: The [ProfileModel][]{ data-preview } to create or update.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def remove_profile(self, profile_id: int) -> None:
        """Delete all profiles with the given `profile_id` from the database.

        Args:
            profile_id: The identifier of the profile to delete.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def fetch_open_tickets(self) -> list[TicketModel]:
        """Return all currently open tickets for this `bot_id`.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def persist_ticket(self, ticket: TicketModel) -> None:
        """Insert a new [TicketModel][]{ data-preview } into the database.

        Args:
            ticket: The [TicketModel][]{ data-preview } to persist.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
            TicketCreationError: If a ticket already exists with the same key or channel ID.
        """

    @abstractmethod
    async def close_ticket(
        self,
        ticket_key: str,
        closer: TicketUserModel,
        ticket_status: TicketStatus,
    ) -> None:
        """Mark a ticket as closed in the database.

        Args:
            ticket_key: The key of the ticket to close.
            closer: The [TicketUserModel][]{ data-preview } who is closing the ticket.
            ticket_status: The status to set. This cannot be [`TicketStatus.open`][].

        Raises:
            ValueError: If `ticket_status` is [`TicketStatus.open`][].
            TicketNotFoundError: If no ticket with the given key exists.
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def update_ticket_log_message(self, ticket_key: str, message_id: int | None) -> None:
        """Update the `log_channel_message_id` field for a ticket.

        Args:
            ticket_key: The key of the ticket to update.
            message_id: The new message ID, or `None` to clear.

        Raises:
            TicketNotFoundError: If the ticket is not found.
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def fetch_ticket_by_channel(self, channel_id: int) -> TicketModel | None:
        """Fetch any ticket (open or closed) by its channel ID.

        Args:
            channel_id: The channel to search for.

        Returns:
            TicketModel: The matching ticket.
            None: If no ticket was found.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def fetch_ticket_by_key(self, key: str) -> TicketModel | None:
        """Fetch any ticket (open or closed) by its key.

        Args:
            key: The ticket key to search for.

        Returns:
            TicketModel: The matching ticket.
            None: If no ticket was found.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @overload
    async def fetch_tickets_by_recipient(
        self, recipient_id: int, *, count: Literal[True], only_closed: bool = False
    ) -> int: ...

    @overload
    async def fetch_tickets_by_recipient(
        self, recipient_id: int, *, count: Literal[False], only_closed: bool = False
    ) -> list[TicketModel]: ...

    @abstractmethod
    async def fetch_tickets_by_recipient(
        self, recipient_id: int, *, count: bool = False, only_closed: bool = False
    ) -> int | list[TicketModel]:
        """Fetch all tickets associated with a recipient.

        Args:
            recipient_id: The user ID to search for.
            count: If `True`, return the count instead of the list.
            only_closed: If `True`, exclude open tickets.

        Returns:
            int: Total count when `count` is `True`.
            list[TicketModel]: The matching tickets when `count` is `False`.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """

    @abstractmethod
    async def persist_message(self, ticket_message: TicketMessageModel) -> None:
        """Save a message to the database.

        The backend should update all user data referenced within the `ticket_message`.

        Args:
            ticket_message: The [TicketMessageModel][]{ data-preview } to persist.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
