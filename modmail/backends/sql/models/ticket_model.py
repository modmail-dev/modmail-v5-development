"""SQLAlchemy model for ticket users.

This module defines the SQLTicketUserTable class, which represents
the ticket user table in the database.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.backends.common import TicketModel
from modmail.enum import TicketStatus

from .base import SQLBase
from .ticket_recipient_model import SQLTicketRecipientTable
from .ticket_user_model import SQLTicketUserTable

__all__ = ["SQLTicketTable"]


class SQLTicketTable(SQLBase):
    """SQL model representing a ticket.

    This model stores information about a ticket, including its ID, key,
    participants, channel ID, creation time, status, and other metadata.

    Attributes:
        bot_id: The unique identifier of the bot.
        key: The unique key for the ticket.
        recipients: List of users involved in the ticket.
        channel_id: The ID of the channel associated with the ticket.
        created_at: The timestamp when the ticket was created.
        created_by: The user who created the ticket.
        status: The current status of the ticket (open, closed, etc.).
        closed_by: The user who closed the ticket (if applicable).
        closed_at: The timestamp when the ticket was closed (if applicable).
        title: An optional title for the ticket.
        nsfw: A boolean indicating if the ticket is NSFW (not safe for work).
    """

    __tablename__ = "ticket"

    bot_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(12), primary_key=True)

    recipients: Mapped[list[SQLTicketRecipientTable]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )
    channel_id: Mapped[int]

    created_at: Mapped[datetime]
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    created_by: Mapped[SQLTicketUserTable] = relationship(foreign_keys=[created_by_id], lazy="joined")

    closed_at: Mapped[datetime | None]
    closed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    closed_by: Mapped[SQLTicketUserTable | None] = relationship(foreign_keys=[closed_by_id], lazy="joined")

    status: Mapped[TicketStatus]
    title: Mapped[str | None]
    nsfw: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (UniqueConstraint("bot_id", "channel_id", name="uq_ticket_channel"),)

    async def get_model(self) -> TicketModel:
        """Get the ticket model associated with this ticket.

        Returns:
            The converted TicketModel.
        """
        recipients = await asyncio.gather(*[recipient.get_model() for recipient in self.recipients])
        created_by = await self.created_by.get_model()
        closed_by = await self.closed_by.get_model() if self.closed_by else None

        return TicketModel(
            bot_id=self.bot_id,
            key=self.key,
            recipients=recipients,
            channel_id=self.channel_id,
            created_at=self.created_at,
            created_by=created_by,
            status=self.status,
            closed_by=closed_by,
            closed_at=self.closed_at,
            title=self.title,
            nsfw=self.nsfw,
        )
