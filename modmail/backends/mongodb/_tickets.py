"""Persists tickets through their full lifecycle."""

from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING, Literal, cast, overload

import pymongo.errors
from beanie import UpdateResponse
from bson import DBRef

from modmail.enum import TicketStatus
from modmail.errors import DatabaseOperationError, TicketNotFoundError

from ._base import MongoDBBackendBase
from .models import MongoDBTicketDocument, MongoDBTicketMessageDocument, MongoDBTicketUserDocument

if TYPE_CHECKING:
    from beanie.odm.queries.update import UpdateOne
    from pymongo.results import UpdateResult

    from modmail.backends.common import TicketMessageModel, TicketModel, TicketUserModel


class MongoDBTicketsMixin(MongoDBBackendBase):
    """MongoDB mixin implementing all ticket and message persistence methods."""

    async def fetch_open_tickets(self) -> list[TicketModel]:
        """Return all currently open tickets for this `bot_id`.

        Returns:
            list[TicketModel]: All open [TicketModel][]{ data-preview } instances for this `bot_id`.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            docs = await MongoDBTicketDocument.find(
                MongoDBTicketDocument.bot_id == self._config.bot.bot_id,
                MongoDBTicketDocument.status == TicketStatus.open,
                fetch_links=True,
            ).to_list()
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to fetch open tickets") from exc
        return [doc.to_model() for doc in docs]

    async def persist_ticket(self, ticket: TicketModel) -> None:
        """Insert a new ticket document into MongoDB.

        Args:
            ticket: The [TicketModel][]{ data-preview } to persist.

        Raises:
            TicketCreationError: If a ticket with the same key already exists.
            DatabaseOperationError: If an unexpected database error occurs.
        """
        await MongoDBTicketDocument.put_model(ticket)

    async def close_ticket(self, ticket_key: str, closer: TicketUserModel, ticket_status: TicketStatus) -> None:
        """Mark a ticket as closed in MongoDB.

        Args:
            ticket_key: The key of the ticket to close.
            closer: The [TicketUserModel][]{ data-preview } who is closing the ticket.
            ticket_status: The terminal status to set (must not be [`TicketStatus.open`][]).

        Raises:
            ValueError: If `ticket_status` is [`TicketStatus.open`][].
            TicketNotFoundError: If no ticket with the given key exists.
            DatabaseOperationError: If an unexpected database error occurs.
        """
        if ticket_status == TicketStatus.open:
            raise ValueError("Ticket status cannot be open.")

        closer_ref = DBRef("TicketUser", closer.user_id)
        try:
            _, update_result = cast(
                "tuple[MongoDBTicketUserDocument, UpdateResult]",
                await asyncio.gather(
                    MongoDBTicketUserDocument.put_model(closer),
                    cast(
                        "UpdateOne",
                        MongoDBTicketDocument.find_one(
                            MongoDBTicketDocument.bot_id == self._config.bot.bot_id,
                            MongoDBTicketDocument.key == ticket_key,
                        ).update(
                            {
                                "$set": {
                                    "status": ticket_status,
                                    "closed_at": datetime.datetime.now(tz=datetime.UTC),
                                    "closed_by": closer_ref,
                                }
                            },
                            response_type=UpdateResponse.UPDATE_RESULT,
                        ),
                    ),
                ),
            )
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to close ticket") from exc

        if update_result.matched_count == 0:
            raise TicketNotFoundError(f"Ticket {ticket_key!r} not found in database.")

    async def update_ticket_log_message(self, ticket_key: str, message_id: int | None) -> None:
        """Update `log_channel_message_id` for a ticket document.

        Args:
            ticket_key: The key of the ticket to update.
            message_id: The new Discord message ID for the log entry, or `None` to clear.

        Raises:
            TicketNotFoundError: If no ticket with that key exists for this `bot_id`.
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            result = cast(
                "UpdateResult",
                await cast(
                    "UpdateOne",
                    MongoDBTicketDocument.find_one(
                        MongoDBTicketDocument.bot_id == self._config.bot.bot_id,
                        MongoDBTicketDocument.key == ticket_key,
                    ).update(
                        {"$set": {"log_channel_message_id": message_id}},
                        response_type=UpdateResponse.UPDATE_RESULT,
                    ),
                ),
            )
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to update ticket log message") from exc

        if result.matched_count == 0:
            raise TicketNotFoundError(f"Ticket {ticket_key!r} not found.")

    async def fetch_ticket_by_channel(self, channel_id: int) -> TicketModel | None:
        """Fetch any ticket (open or closed) by its associated channel ID.

        Args:
            channel_id: The Discord channel ID to search for.

        Returns:
            TicketModel: The matching ticket.
            None: If no ticket has this channel ID.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            doc = await MongoDBTicketDocument.find_one(
                MongoDBTicketDocument.bot_id == self._config.bot.bot_id,
                MongoDBTicketDocument.channel_id == channel_id,
                fetch_links=True,
            )
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to fetch ticket by channel") from exc
        if doc is None:
            return None
        return doc.to_model()

    async def fetch_ticket_by_key(self, key: str) -> TicketModel | None:
        """Fetch any ticket (open or closed) by its unique key.

        Args:
            key: The ticket key to search for.

        Returns:
            TicketModel: The matching ticket.
            None: If no ticket has this key.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            doc = await MongoDBTicketDocument.find_one(
                MongoDBTicketDocument.bot_id == self._config.bot.bot_id,
                MongoDBTicketDocument.key == key,
                fetch_links=True,
            )
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to fetch ticket by key") from exc
        if doc is None:
            return None
        return doc.to_model()

    @overload
    async def fetch_tickets_by_recipient(
        self, recipient_id: int, *, count: Literal[True], only_closed: bool = False
    ) -> int: ...

    @overload
    async def fetch_tickets_by_recipient(
        self, recipient_id: int, *, count: Literal[False], only_closed: bool = False
    ) -> list[TicketModel]: ...

    async def fetch_tickets_by_recipient(
        self, recipient_id: int, *, count: bool = False, only_closed: bool = False
    ) -> int | list[TicketModel]:
        """Fetch all tickets associated with a recipient user.

        Args:
            recipient_id: The Discord user ID to search for in ticket recipients.
            count: If `True`, return the total count instead of the list of models.
            only_closed: If `True`, exclude tickets that are still open.

        Returns:
            int: Total count when `count` is `True`.
            list[TicketModel]: The matching [TicketModel][]{ data-preview } instances otherwise.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        conditions = [
            MongoDBTicketDocument.bot_id == self._config.bot.bot_id,
            cast("MongoDBTicketUserDocument", cast("object", MongoDBTicketDocument.recipients)).id == recipient_id,
        ]
        if only_closed:
            conditions.append(MongoDBTicketDocument.status != TicketStatus.open)

        try:
            if count:
                return await MongoDBTicketDocument.find(*conditions).count()

            docs = await MongoDBTicketDocument.find(*conditions, fetch_links=True).to_list()
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to fetch tickets by recipient") from exc

        return [doc.to_model() for doc in docs]

    async def persist_message(self, ticket_message: TicketMessageModel) -> None:
        """Insert a new ticket message document into MongoDB.

        Args:
            ticket_message: The [TicketMessageModel][]{ data-preview } to persist.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        await MongoDBTicketMessageDocument.put_model(ticket_message)
