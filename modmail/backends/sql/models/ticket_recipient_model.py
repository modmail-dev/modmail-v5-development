"""Represents a recipient in a ticket.

This module defines the SQLTicketRecipientTable class, which represents
the ticket recipient table in the database. It includes information about
the recipient user, the associated ticket, and other metadata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import SQLBase
from .ticket_user_model import SQLTicketUserTable

if TYPE_CHECKING:
    from modmail.backends.common import TicketUserModel

__all__ = ["SQLTicketRecipientTable"]


class SQLTicketRecipientTable(SQLBase):
    """SQL model representing a recipient in a ticket.

    This model stores information about a recipient user in a ticket,
    including their user ID, the associated ticket, and other metadata.

    Attributes:
        id: A surrogate key for this table.
        bot_id: The unique identifier of the bot.
        ticket_key: The unique key for the ticket.
        user_id: The ID of the recipient user.
        user: The recipient user associated with this ticket.
    """

    __tablename__ = "ticket_recipient"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_id: Mapped[int]
    ticket_key: Mapped[str] = mapped_column(String(12))
    user_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    user: Mapped[SQLTicketUserTable] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("bot_id", "ticket_key", "user_id", name="uq_ticket_recipient"),
        ForeignKeyConstraint(
            ["bot_id", "ticket_key"],
            ["ticket.bot_id", "ticket.key"],
            name="fk_ticket_recipient_ticket",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
    )

    async def get_model(self) -> TicketUserModel:
        """Get the ticket user model associated with this recipient.

        Returns:
            TicketUserModel: The ticket user model.
        """
        return await self.user.get_model()
