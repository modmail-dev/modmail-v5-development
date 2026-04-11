"""Public interface for database access.

[DBClient][]{ data-preview } provides a high-level interface for database operations
and owns the in-memory caches. Profiles and open tickets use read-through caching
and are fully resynchronized from the database every `_RESYNC_INTERVAL` seconds.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any, Literal, overload

from modmail.enum import ProfileKey, ProfileType, TicketStatus
from modmail.errors import (
    CacheNotReadyError,
    DatabaseConnectionError,
    DatabaseOperationError,
    TicketCreationError,
    TicketRecipientOccupiedError,
)
from modmail.utils import MultiKeyCollection

from .models import ProfileModel, SettingsModel, TicketMessageModel, TicketModel, TicketUserModel

if TYPE_CHECKING:
    # Resolve docs import
    from modmail.errors import (
        InstanceAlreadyRunningError,  # pyright: ignore [reportUnusedImport]  # noqa: F401
        TicketNotFoundError,  # pyright: ignore [reportUnusedImport]  # noqa: F401
    )

    from .db_backend import DBBackend

__all__ = ["DBClient"]

logger = logging.getLogger(__name__)

_RESYNC_INTERVAL: int = 300  # seconds between full cache re-syncs


class DBClient:
    """Public interface for database operations.

    All in-memory caching is managed by this class. The underlying [DBBackend][]{ data-preview } does
    not maintain any caches and callers should interact exclusively with [DBClient][]{ data-preview }.
    """

    def __init__(self, backend: DBBackend) -> None:
        """Initialize the client with the given backend strategy.

        Args:
            backend: The concrete [DBBackend][]{ data-preview }.
        """
        self._backend = backend
        self._settings: SettingsModel | None = None
        self._profiles_mapping: dict[ProfileKey, ProfileModel] | None = None
        self._open_tickets: MultiKeyCollection[TicketModel] = MultiKeyCollection("key", "channel_id")
        self._resync_task: asyncio.Task[None] | None = None
        self._cache_ready: asyncio.Event = asyncio.Event()

    # -------------------------------------------------------------------------
    # Connection
    # -------------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the database and populate all caches.

        Connects the backend, performs an initial full sync of settings, profiles,
        and open tickets, then starts the periodic re-sync task. Sets the internal
        cache-ready event so that callers awaiting [`wait_until_ready`][] are unblocked.

        Raises:
            DatabaseConnectionError: If the backend connection fails.
            InstanceAlreadyRunningError: If another live instance is already running.
            DatabaseOperationError: If the initial cache sync fails.
        """
        await self._backend.connect()
        await self._sync_all()
        self._cache_ready.set()
        self._resync_task = asyncio.create_task(self._resync_loop(), name="cache-resync")

    async def disconnect(self) -> None:
        """Disconnect from the database.

        Also stops the cache re-sync task, clears the cache-ready event,
        and releases the instance lock.
        """
        self._cache_ready.clear()
        if self._resync_task is not None:
            self._resync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._resync_task
            self._resync_task = None
        await self._backend.disconnect()

    # -------------------------------------------------------------------------
    # Cache readiness
    # -------------------------------------------------------------------------

    def _require_cache_ready(self) -> None:
        """Raise [CacheNotReadyError][] if the cache has not been populated yet.

        Raises:
            CacheNotReadyError: If [`connect`][] has not completed its initial sync.
        """
        if not self._cache_ready.is_set():
            raise CacheNotReadyError(
                "Cache is not ready. Await connect() or wait_until_ready() before accessing cached data."
            )

    async def wait_until_ready(self, max_wait: float = 30.0) -> None:
        """Wait until the cache has been fully populated.

        Returns immediately if the cache is already ready. Otherwise, blocks until
        [`connect`][] has completed its initial sync of settings, profiles, and
        open tickets.

        Args:
            max_wait: Maximum seconds to wait before raising. Defaults to 30 seconds.

        Raises:
            DatabaseConnectionError: If the cache is not ready within `max_wait` seconds.
        """
        try:
            await asyncio.wait_for(self._cache_ready.wait(), timeout=max_wait)
        except TimeoutError as e:
            raise DatabaseConnectionError(
                f"Cache did not become ready within {max_wait}s. "
                "Ensure connect() has been called and completed successfully."
            ) from e

    async def _sync_all(self, *, suppress_errors: bool = False) -> None:
        """Sync settings, profiles, and open ticket caches concurrently.

        Args:
            suppress_errors: If `True`, log sync failures instead of raising them.
                Used by the background re-sync loop so one failure doesn't abort the others.

        Raises:
            DatabaseOperationError: If any sync fails and `suppress_errors` is `False`.
        """
        names = ("settings", "profiles", "open tickets")
        results = await asyncio.gather(
            self.sync_settings(),
            self.sync_profiles(),
            self.sync_open_tickets(),
            return_exceptions=True,
        )
        for name, result in zip(names, results, strict=True):
            if isinstance(result, BaseException):
                if suppress_errors:
                    logger.warning("Periodic cache re-sync failed for %s.", name, exc_info=result)
                else:
                    raise result

    async def _resync_loop(self) -> None:
        """Periodically re-sync all caches from the database.

        Waits `_RESYNC_INTERVAL` seconds between syncs, so the first cycle runs
        after the initial sync in [`connect`][]{ data-preview } rather than immediately
        on startup. Each cache is synced independently, so a failure in one does
        not block the others.
        """
        while True:
            await asyncio.sleep(_RESYNC_INTERVAL)
            await self._sync_all(suppress_errors=True)

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------

    @property
    def settings(self) -> SettingsModel:
        """The cached [SettingsModel][]{ data-preview }.

        The cache is populated on bot start and resynced every `_RESYNC_INTERVAL`.

        Raises:
            CacheNotReadyError: If [`connect`][] has not completed its initial sync.
            RuntimeError: If the cache is missing despite ready. This should never happen.
        """
        self._require_cache_ready()

        if self._settings is None:
            raise RuntimeError("Settings cache is None after cache ready. This should never happen.")
        return self._settings

    async def sync_settings(self) -> None:
        """Update the local cache with the current settings from the database.

        Raises:
            DatabaseOperationError: If the backend fetch call fails.
        """
        self._settings = await self._backend.fetch_settings()
        logger.debug("Synchronized settings from database.")

    async def update_settings(self, **kwargs: Any) -> None:
        """Apply field updates to the settings and persist them.

        Applies `**kwargs` to the [SettingsModel][]{ data-preview } and updates the cache on success.
        See [SettingsModel][]{ data-preview } for the full list of settable fields.

        On failure, the cache is refreshed from the database to keep it consistent.

        Args:
            **kwargs: Field names and new values to apply to the settings model.

        Raises:
            DatabaseOperationError: If the backend persist call fails.
        """
        current = self.settings
        new_settings = SettingsModel(**current.model_dump(exclude=dict.fromkeys(kwargs, True)), **kwargs)
        try:
            await self._backend.persist_settings(new_settings)
        except DatabaseOperationError:
            logger.warning("Failed to persist settings, re-syncing from database.", exc_info=True)
            await self.sync_settings()
            raise
        self._settings = new_settings
        logger.debug("Updated settings: %s.", kwargs, stacklevel=2)

    # -------------------------------------------------------------------------
    # Profiles
    # -------------------------------------------------------------------------

    @property
    def profiles(self) -> list[ProfileModel]:
        """All cached profiles.

        The cache is populated on bot start and resynced every `_RESYNC_INTERVAL`.

        Raises:
            CacheNotReadyError: If [`connect`][] has not completed its initial sync.
        """
        return list(self._profiles.values())

    @property
    def _profiles(self) -> dict[ProfileKey, ProfileModel]:
        """The cached profiles as a dict mapping [`ProfileKey`][] to [ProfileModel][]{ data-preview }.

        The cache is populated on bot start and resynced every `_RESYNC_INTERVAL`.

        Raises:
            CacheNotReadyError: If [`connect`][] has not completed its initial sync.
            RuntimeError: If the cache is missing despite ready. This should never happen.
        """
        self._require_cache_ready()
        if self._profiles_mapping is None:
            raise RuntimeError("Profiles cache is None after cache ready. This should never happen.")
        return self._profiles_mapping

    async def sync_profiles(self) -> None:
        """Update the local cache with all profiles from the database.

        Raises:
            DatabaseOperationError: If the backend fetch call fails.
        """
        all_profiles = await self._backend.fetch_all_profiles()
        self._profiles_mapping = {ProfileKey(p.profile_id, p.profile_type): p for p in all_profiles}
        logger.debug("Synchronized %d profiles from database.", len(self._profiles_mapping))

    def get_profile(self, profile_id: int, profile_type: ProfileType) -> ProfileModel | None:
        """Look up a [ProfileModel][]{ data-preview } in the local cache.

        Args:
            profile_id: The numeric profile identifier.
            profile_type: [ProfileType][]{ data-preview } to search for.

        Returns:
            ProfileModel: The matching profile.
            None: If no profile with those identifiers is cached.
        """
        return self._profiles.get(ProfileKey(profile_id, profile_type))

    async def update_profile(self, profile: ProfileModel) -> None:
        """Persist a [ProfileModel][]{ data-preview } to the database and update the local cache.

        Args:
            profile: The profile to create or update.

        Raises:
            DatabaseOperationError: If the backend persist call fails.
        """
        await self._backend.persist_profile(profile)
        self._profiles[ProfileKey(profile.profile_id, profile.profile_type)] = profile
        logger.debug("Updated profile %s/%s in cache.", profile.profile_id, profile.profile_type, stacklevel=2)

    async def delete_profile(self, profile_id: int) -> None:
        """Remove a [ProfileModel][]{ data-preview } from the database and the local cache.

        Args:
            profile_id: The identifier of the profile to delete. All profile
                types sharing this ID are removed.

        Raises:
            DatabaseOperationError: If the backend remove call fails.
        """
        await self._backend.remove_profile(profile_id)
        for key in [k for k in self._profiles if k.profile_id == profile_id]:
            del self._profiles[key]
        logger.debug("Deleted profile %d from cache.", profile_id, stacklevel=2)

    # -------------------------------------------------------------------------
    # Tickets
    # -------------------------------------------------------------------------

    @property
    def open_tickets(self) -> list[TicketModel]:
        """All cached open tickets.

        The cache is populated on bot start and resynced every `_RESYNC_INTERVAL`.

        Raises:
            CacheNotReadyError: If [`connect`][] has not completed its initial sync.
        """
        self._require_cache_ready()
        return list(self._open_tickets)

    async def sync_open_tickets(self) -> None:
        """Update the local cache with all open tickets from the database.

        Raises:
            DatabaseOperationError: If the backend fetch call fails.
        """
        tickets = await self._backend.fetch_open_tickets()
        cache: MultiKeyCollection[TicketModel] = MultiKeyCollection("key", "channel_id")
        for ticket in tickets:
            cache.add(ticket, key=ticket.key, channel_id=ticket.channel_id)
        self._open_tickets = cache
        logger.debug("Synchronized %d open tickets from database.", len(self._open_tickets))

    async def get_ticket_by_recipient(self, recipient_id: int) -> TicketModel | None:
        """Find an open [TicketModel][]{ data-preview } that has the given user as a recipient.

        Only searches the in-memory cache. Closed tickets are not included.

        Args:
            recipient_id: The Discord user ID to search for.

        Returns:
            TicketModel: The matching open ticket.
            None: If no open ticket has this recipient.

        Raises:
            CacheNotReadyError: If [`connect`][] has not completed its initial sync.
        """
        self._require_cache_ready()
        for ticket in self._open_tickets:
            if any(r.user_id == recipient_id for r in ticket.recipients):
                return ticket
        return None

    async def get_ticket_by_channel(self, channel_id: int, *, only_open: bool = True) -> TicketModel | None:
        """Find a [TicketModel][]{ data-preview } by its associated Discord channel ID.

        Checks the open-ticket cache first. Pass `only_open=False` to also search
        the database for closed tickets.

        Args:
            channel_id: The Discord channel ID to search for.
            only_open: When `False`, also searches the database for closed tickets.

        Returns:
            TicketModel: The matching ticket.
            None: If no ticket was found.

        Raises:
            CacheNotReadyError: If [`connect`][] has not completed its initial sync.
            DatabaseOperationError: If `only_open` is `False` and the database query fails.
        """
        self._require_cache_ready()
        cached = self._open_tickets.get(channel_id=channel_id)
        if cached is not None:
            return cached
        if only_open:
            return None
        logger.debug("Cache miss for channel %d, querying database.", channel_id, stacklevel=2)
        return await self._backend.fetch_ticket_by_channel(channel_id)

    async def get_ticket_by_key(self, key: str, *, only_open: bool = True) -> TicketModel | None:
        """Find a [TicketModel][]{ data-preview } by its unique key.

        Checks the open-ticket cache first. Pass `only_open=False` to also search
        the database for closed tickets.

        Args:
            key: The ticket key to search for.
            only_open: When `False`, also searches the database for closed tickets.

        Returns:
            TicketModel: The matching ticket.
            None: If no ticket was found.

        Raises:
            CacheNotReadyError: If [`connect`][] has not completed its initial sync.
            DatabaseOperationError: If `only_open` is `False` and the database query fails.
        """
        self._require_cache_ready()
        cached = self._open_tickets.get(key=key)
        if cached is not None:
            return cached
        if only_open:
            return None
        logger.debug("Cache miss for key %r, querying database.", key, stacklevel=2)
        return await self._backend.fetch_ticket_by_key(key)

    @overload
    async def get_all_tickets_by_recipient(
        self, recipient_id: int, *, count: Literal[True], only_closed: bool = False
    ) -> int: ...

    @overload
    async def get_all_tickets_by_recipient(
        self, recipient_id: int, *, count: Literal[False], only_closed: bool = False
    ) -> list[TicketModel]: ...

    async def get_all_tickets_by_recipient(
        self, recipient_id: int, *, count: bool = False, only_closed: bool = False
    ) -> int | list[TicketModel]:
        """Fetch all tickets associated with a recipient from the database.

        Always queries the database directly because closed tickets are not held in the cache.

        Use [`get_ticket_by_recipient`][]{ data-preview } to search the cache
        for the recipient's current open ticket.

        Args:
            recipient_id: The Discord user ID to search for.
            count: If `True`, return the total count instead of the list of tickets.
            only_closed: If `True`, exclude open tickets from the results.

        Returns:
            int: Total count when `count` is `True`.
            list[TicketModel]: The matching tickets when `count` is `False`.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        logger.debug(
            "Fetching tickets for recipient %d (count=%s, only_closed=%s).",
            recipient_id,
            count,
            only_closed,
            stacklevel=2,
        )
        return await self._backend.fetch_tickets_by_recipient(recipient_id, count=count, only_closed=only_closed)

    async def create_ticket(self, ticket: TicketModel) -> None:
        """Create a new [TicketModel][]{ data-preview } in the database.

        Args:
            ticket: The ticket to create.

        Raises:
            CacheNotReadyError: If [`connect`][] has not completed its initial sync.
            DatabaseOperationError: If an unexpected database error occurs.
            TicketCreationError: If another open ticket shares the same channel ID.
            TicketRecipientOccupiedError: If any recipient already has an open ticket.
        """
        self._require_cache_ready()
        for cached in self._open_tickets:
            if cached.channel_id == ticket.channel_id:
                raise TicketCreationError("Ticket with this channel ID already exists.")
            if any(new_r.user_id == old_r.user_id for old_r in cached.recipients for new_r in ticket.recipients):
                raise TicketRecipientOccupiedError("An open ticket with this recipient already exists.")

        await self._backend.persist_ticket(ticket)

        if ticket.status == TicketStatus.open:
            self._open_tickets.add(ticket, key=ticket.key, channel_id=ticket.channel_id)
        logger.info("Created ticket %s for %s.", ticket.key, ticket.recipients, stacklevel=2)

    async def set_ticket_log_channel_message_id(self, ticket_key: str, message_id: int | None) -> None:
        """Update the log channel message ID for a ticket.

        Args:
            ticket_key: The key of the ticket to update.
            message_id: The new Discord message ID for the log entry, or `None` to clear.

        Raises:
            TicketNotFoundError: If no ticket with the given key exists.
            DatabaseOperationError: If an unexpected database error occurs.
        """
        await self._backend.update_ticket_log_message(ticket_key, message_id)
        cached = self._open_tickets.get(key=ticket_key)
        if cached is not None:
            updated = cached.model_copy(update={"log_channel_message_id": message_id})
            self._open_tickets.remove("key", ticket_key)
            self._open_tickets.add(updated, key=updated.key, channel_id=updated.channel_id)
        logger.debug("Set log channel message ID for ticket %s to %s.", ticket_key, message_id, stacklevel=2)

    async def save_message(self, ticket_message: TicketMessageModel) -> None:
        """Save a [TicketMessageModel][]{ data-preview } to the database.

        Messages are not cached and are written straight through to the backend.

        Args:
            ticket_message: The [TicketMessageModel][]{ data-preview } to persist.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        await self._backend.persist_message(ticket_message)
        logger.debug(
            "Persisted message %s in ticket %s.",
            ticket_message.message_id,
            ticket_message.ticket_key,
            stacklevel=2,
        )

    async def close_ticket(
        self,
        ticket_key: str,
        closer: TicketUserModel,
        *,
        ticket_status: TicketStatus = TicketStatus.closed_by_command,
    ) -> None:
        """Close a [TicketModel][]{ data-preview } in the database.

        Args:
            ticket_key: The key of the ticket to close.
            closer: The [TicketUserModel][]{ data-preview } who is closing the ticket.
            ticket_status: The terminal status to assign (default: [`TicketStatus.closed_by_command`][]).

        Raises:
            ValueError: If `ticket_status` is [`TicketStatus.open`][].
            TicketNotFoundError: If no ticket with the given key exists.
            DatabaseOperationError: If an unexpected database error occurs.
        """
        await self._backend.close_ticket(ticket_key, closer, ticket_status)
        try:
            self._open_tickets.remove("key", ticket_key)
        except KeyError:
            logger.debug("Ticket %s not found in cache during close.", ticket_key)
        logger.debug("Closed ticket %s.", ticket_key, stacklevel=2)
