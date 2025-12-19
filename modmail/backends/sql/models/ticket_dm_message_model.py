"""Ticket Direct Message SQL Model.

This module defines the SQLTicketDMMessageTable class, which represents
the ticket direct message table in the database.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import SQLBase
from .ticket_message_model import SQLTicketMessageTable
from .ticket_user_model import SQLTicketUserTable

__all__ = ["SQLTicketDMMessageTable"]


class SQLTicketDMMessageTable(SQLBase):
    """SQL model representing a direct message in a ticket.

    This model stores information about a direct message, including its ID,
    the associated ticket message, the recipient user, and other metadata.

    Attributes:
        message_id: The unique identifier of the direct message.
        ticket_message_ref_id: The ID of the associated ticket message row.
        ticket_message: The ticket message associated with this direct message.
        recipient_id: The ID of the recipient user.
        recipient: The recipient user of this direct message.
    """

    __tablename__ = "ticket_dm_message"

    message_id: Mapped[int] = mapped_column(primary_key=True)
    ticket_message_ref_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_message.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    ticket_message: Mapped[SQLTicketMessageTable] = relationship(back_populates="dm_messages", lazy="joined")
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    recipient: Mapped[SQLTicketUserTable] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("message_id", "ticket_message_ref_id", name="uq_ticket_dm_message"),)
