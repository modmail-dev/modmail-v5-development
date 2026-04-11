"""SQLAlchemy model for the ticket message table."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.enum import TicketMessageType

from .base import TABLE_OPTS, Snowflake, SQLBase
from .ticket_dm_message_model import SQLTicketDMMessageTable
from .ticket_user_model import SQLTicketUserTable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from modmail.backends.common.models import TicketMessageModel


__all__ = ["SQLTicketMessageTable"]


class SQLTicketMessageTable(SQLBase):
    """SQL model for the ticket message table.

    A unique constraint on ([`bot_id`][], [`ticket_key`][], [`message_id`][]) still prevents
    duplicate entries. DM delivery records are stored in a child
    [SQLTicketDMMessageTable][]{ data-preview } table.

    **Primary key:** [`id`][] (surrogate; Discord message IDs are not unique across bots sharing
    the same database).
    """

    __tablename__ = "ticket_message"

    # Not using `message_id` as primary key because multiple bots may have the same message ID.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    """Surrogate primary key."""
    bot_id: Mapped[Snowflake]
    """Discord application ID of the bot that owns this message."""
    ticket_key: Mapped[str] = mapped_column(String(12))
    """Key of the parent ticket."""

    message_id: Mapped[Snowflake]
    """Discord message ID in the staff-side ticket channel."""
    dm_messages: Mapped[list[SQLTicketDMMessageTable]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="ticket_message",
        lazy="selectin",
    )
    """[SQLTicketDMMessageTable][]{ data-preview } rows, one per DM delivery."""

    author_id: Mapped[Snowflake] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    """Discord snowflake ID of the message author."""
    author: Mapped[SQLTicketUserTable] = relationship(foreign_keys=[author_id], lazy="joined")
    """[SQLTicketUserTable][]{ data-preview } who sent the message."""

    content: Mapped[str] = mapped_column(String(4096))
    """Raw text content of the message."""
    created_at: Mapped[datetime.datetime]
    """UTC-aware timestamp when the message was sent."""

    edited_at: Mapped[datetime.datetime | None]
    """UTC-aware timestamp of the most recent edit (`None` if [`edited_by`][] is unset)."""
    edited_by_id: Mapped[Snowflake | None] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    """Discord snowflake ID of the last editor (`None` if [`edited_at`][] is unset)."""
    edited_by: Mapped[SQLTicketUserTable | None] = relationship(foreign_keys=[edited_by_id], lazy="joined")
    """[SQLTicketUserTable][]{ data-preview } who made the edit (`None` if [`edited_at`][] is unset)."""

    deleted_at: Mapped[datetime.datetime | None]
    """UTC-aware timestamp when the message was deleted (`None` if [`deleted_by`][] is unset)."""
    deleted_by_id: Mapped[Snowflake | None] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    """Discord snowflake ID of the user who deleted the message (`None` if [`deleted_at`][] is unset)."""
    deleted_by: Mapped[SQLTicketUserTable | None] = relationship(foreign_keys=[deleted_by_id], lazy="joined")
    """[SQLTicketUserTable][]{ data-preview } who deleted the message
    (`None` if [`deleted_at`][] is unset).
    """

    type: Mapped[TicketMessageType]
    """Message type as a [TicketMessageType][]{ data-preview }."""

    __table_args__ = (
        UniqueConstraint("bot_id", "ticket_key", "message_id", name="uq_ticket_message"),
        ForeignKeyConstraint(
            ["bot_id", "ticket_key"],
            ["ticket.bot_id", "ticket.key"],
            name="fk_ticket_message_ticket",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        Index("ix_ticket_message_type", "bot_id", "ticket_key", "type"),
        Index("ix_ticket_message_author", "bot_id", "ticket_key", "author_id"),
        TABLE_OPTS,
    )

    @classmethod
    async def put_model(cls, model: TicketMessageModel, session: AsyncSession) -> None:
        """Insert a ticket message and its per-recipient DM records into the database.

        Note:
            Must be called inside an active `session.begin()` block.

        Args:
            model: The ticket message to persist.
            session: An open [AsyncSession][] with an active transaction.

        Raises:
            RuntimeError: If called outside an active `session.begin()` block.
            sqlalchemy.exc.SQLAlchemyError: If an unexpected database error occurs.
        """
        from .ticket_dm_message_model import SQLTicketDMMessageTable

        if not session.in_transaction():
            raise RuntimeError("put_model must be called inside an active session.begin() block")
        await SQLTicketUserTable.put_many(
            model.author,
            *[dm.recipient for dm in model.dm_messages],
            *([model.edited_by] if model.edited_by else []),
            *([model.deleted_by] if model.deleted_by else []),
            session=session,
        )
        session.add(
            cls(
                bot_id=model.bot_id,
                ticket_key=model.ticket_key,
                message_id=model.message_id,
                author_id=model.author.user_id,
                content=model.content,
                created_at=model.created_at,
                edited_at=model.edited_at,
                edited_by_id=model.edited_by.user_id if model.edited_by else None,
                deleted_at=model.deleted_at,
                deleted_by_id=model.deleted_by.user_id if model.deleted_by else None,
                type=model.type,
                dm_messages=[
                    SQLTicketDMMessageTable(
                        message_id=dm.message_id,
                        recipient_id=dm.recipient.user_id,
                    )
                    for dm in model.dm_messages
                ],
            )
        )
