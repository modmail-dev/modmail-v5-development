"""Persists tickets through their full lifecycle."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Literal, cast, overload

import sqlalchemy.exc
from sqlalchemy import and_, func, select, update

from modmail.enum import TicketStatus
from modmail.errors import DatabaseOperationError, TicketNotFoundError

from ._base import SQLBackendBase
from .models import SQLTicketMessageTable, SQLTicketRecipientTable, SQLTicketTable, SQLTicketUserTable

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult

    from modmail.backends.common import TicketMessageModel, TicketModel, TicketUserModel


class SQLTicketsMixin(SQLBackendBase):
    """SQL mixin implementing all ticket and message persistence methods."""

    async def fetch_open_tickets(self) -> list[TicketModel]:
        """Return all currently open tickets for this `bot_id`.

        Returns:
            list[TicketModel]: All open [TicketModel][]{ data-preview } instances for this `bot_id`.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            async with self.session() as session:
                rows = (
                    (
                        await session.execute(
                            select(SQLTicketTable).where(
                                and_(
                                    SQLTicketTable.bot_id == self._config.bot.bot_id,
                                    SQLTicketTable.status == TicketStatus.open,
                                )
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                models = [row.to_model() for row in rows]
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to fetch open tickets") from exc
        return models

    async def persist_ticket(self, ticket: TicketModel) -> None:
        """Insert a new ticket and its recipient records into the database.

        Args:
            ticket: The [TicketModel][]{ data-preview } to persist.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            async with self.session() as session, session.begin():
                await SQLTicketTable.put_model(ticket, session)
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to persist ticket") from exc

    async def close_ticket(self, ticket_key: str, closer: TicketUserModel, ticket_status: TicketStatus) -> None:
        """Mark a ticket as closed in the database.

        Upserts the closer into [SQLTicketUserTable][]{ data-preview }, then
        updates the ticket's `status`, `closed_at`, and `closed_by_id`.
        All changes are made in a single transaction.

        Args:
            ticket_key: The key of the ticket to close.
            closer: The [TicketUserModel][]{ data-preview } who is closing the ticket.
            ticket_status: The terminal status to set (must not be [`TicketStatus.open`][]).

        Raises:
            ValueError: If `ticket_status` is [`TicketStatus.open`][].
            TicketNotFoundError: If no ticket with the given key exists for this `bot_id`.
            DatabaseOperationError: If an unexpected database error occurs.
        """
        if ticket_status == TicketStatus.open:
            raise ValueError("Ticket status cannot be open.")

        try:
            async with self.session() as session, session.begin():
                await SQLTicketUserTable.put_many(closer, session=session)
                result = cast(
                    "CursorResult[Any]",
                    await session.execute(
                        update(SQLTicketTable)
                        .where(
                            SQLTicketTable.bot_id == self._config.bot.bot_id,
                            SQLTicketTable.key == ticket_key,
                        )
                        .values(
                            status=ticket_status,
                            closed_at=datetime.datetime.now(datetime.UTC),
                            closed_by_id=closer.user_id,
                        )
                    ),
                )
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to close ticket") from exc
        if result.rowcount == 0:
            raise TicketNotFoundError(f"Ticket {ticket_key!r} not found in database.")

    async def update_ticket_log_message(self, ticket_key: str, message_id: int | None) -> None:
        """Update `log_channel_message_id` for a ticket row.

        Args:
            ticket_key: The key of the ticket to update.
            message_id: The new Discord message ID for the log entry, or `None` to clear.

        Raises:
            TicketNotFoundError: If no ticket with that key exists for this `bot_id`.
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            async with self.session() as session, session.begin():
                result = cast(
                    "CursorResult[Any]",
                    await session.execute(
                        update(SQLTicketTable)
                        .where(
                            SQLTicketTable.bot_id == self._config.bot.bot_id,
                            SQLTicketTable.key == ticket_key,
                        )
                        .values(log_channel_message_id=message_id)
                    ),
                )
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to update ticket log message") from exc
        if result.rowcount == 0:
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
            async with self.session() as session:
                row = (
                    await session.execute(
                        select(SQLTicketTable).where(
                            and_(
                                SQLTicketTable.bot_id == self._config.bot.bot_id,
                                SQLTicketTable.channel_id == channel_id,
                            )
                        )
                    )
                ).scalar_one_or_none()
                model = row.to_model() if row is not None else None
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to fetch ticket by channel") from exc
        return model

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
            async with self.session() as session:
                row = await session.get(SQLTicketTable, (self._config.bot.bot_id, key))
                model = row.to_model() if row is not None else None
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to fetch ticket by key") from exc
        return model

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
        where_clause = and_(
            SQLTicketTable.bot_id == self._config.bot.bot_id,
            SQLTicketRecipientTable.user_id == recipient_id,
            *((SQLTicketTable.status != TicketStatus.open,) if only_closed else ()),
        )

        try:
            async with self.session() as session:
                if count:
                    return (
                        await session.execute(
                            select(func.count(SQLTicketTable.key))
                            .select_from(SQLTicketTable)
                            .join(SQLTicketRecipientTable)
                            .where(where_clause)
                        )
                    ).scalar_one()

                rows = (
                    (
                        await session.execute(
                            select(SQLTicketTable).join(SQLTicketRecipientTable).where(where_clause)
                        )
                    )
                    .scalars()
                    .all()
                )
                return [row.to_model() for row in rows]
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to fetch tickets by recipient") from exc

    async def persist_message(self, ticket_message: TicketMessageModel) -> None:
        """Insert a new ticket message and its per-recipient DM records into the database.

        Args:
            ticket_message: The [TicketMessageModel][]{ data-preview } to persist.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            async with self.session() as session, session.begin():
                await SQLTicketMessageTable.put_model(ticket_message, session)
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to persist message") from exc
