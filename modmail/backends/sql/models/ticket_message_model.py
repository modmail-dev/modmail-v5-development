"""SQLAlchemy model for ticket users.

This module defines the SQLTicketUserTable class, which represents
the ticket user table in the database.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.enum import TicketMessageType

from .base import SQLBase
from .ticket_user_model import SQLTicketUserTable

if TYPE_CHECKING:
    from .ticket_dm_message_model import SQLTicketDMMessageTable

__all__ = ["SQLTicketMessageTable"]


class SQLTicketMessageTable(SQLBase):
    """SQL model representing a message in a ticket.

    This model stores information about a message, including its ID, the
    associated ticket, the author, content, timestamps, and other metadata.

    Attributes:
        id: A surrogate key for this table.
        bot_id: The unique identifier of the bot.
        ticket_key: The unique key for the ticket.
        message_id: The unique identifier of the message.
        dm_messages: List of direct messages associated with this message.
        author_id: The ID of the user who authored the message.
        content: The content of the message.
        created_at: The timestamp when the message was created.
        edited_at: The timestamp when the message was last edited.
        edited_by_id: The ID of the user who last edited the message.
        deleted_at: The timestamp when the message was deleted.
        deleted_by_id: The ID of the user who deleted the message.
        type: The type of the message.
    """

    __tablename__ = "ticket_message"

    # Not using `message_id` as primary key because multiple bots may have the same message ID.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_id: Mapped[int]
    ticket_key: Mapped[str] = mapped_column(String(12))

    message_id: Mapped[int]
    dm_messages: Mapped[list[SQLTicketDMMessageTable]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="ticket_message",
        lazy="selectin",
    )

    author_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    author: Mapped[SQLTicketUserTable] = relationship(foreign_keys=[author_id], lazy="joined")

    content: Mapped[str] = mapped_column(String(4096))
    created_at: Mapped[datetime]

    edited_at: Mapped[datetime | None]
    edited_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    edited_by: Mapped[SQLTicketUserTable | None] = relationship(foreign_keys=[edited_by_id], lazy="joined")

    deleted_at: Mapped[datetime | None]
    deleted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    deleted_by: Mapped[SQLTicketUserTable | None] = relationship(foreign_keys=[deleted_by_id], lazy="joined")

    type: Mapped[TicketMessageType]

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
    )
