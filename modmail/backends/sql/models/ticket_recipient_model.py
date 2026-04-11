"""SQLAlchemy model for the ticket recipient table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, ForeignKeyConstraint, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TABLE_OPTS, Snowflake, SQLBase
from .ticket_user_model import SQLTicketUserTable

if TYPE_CHECKING:
    from modmail.backends.common import TicketUserModel

__all__ = ["SQLTicketRecipientTable"]


class SQLTicketRecipientTable(SQLBase):
    """SQL model for the ticket recipient table.

    Links a ticket to its non-staff participant users, one row per recipient.

    **Primary keys:** [`bot_id`][], [`ticket_key`][], [`user_id`][]
    """

    __tablename__ = "ticket_recipient"

    bot_id: Mapped[Snowflake]
    """Discord application ID of the bot that owns this record."""
    ticket_key: Mapped[str] = mapped_column(String(12))
    """Key of the parent ticket."""
    user_id: Mapped[Snowflake] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    """Discord snowflake ID of the recipient."""
    user: Mapped[SQLTicketUserTable] = relationship(lazy="joined")
    """[SQLTicketUserTable][]{ data-preview } for this recipient."""

    __table_args__ = (
        PrimaryKeyConstraint("bot_id", "ticket_key", "user_id"),
        ForeignKeyConstraint(
            ["bot_id", "ticket_key"],
            ["ticket.bot_id", "ticket.key"],
            name="fk_ticket_recipient_ticket",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        TABLE_OPTS,
    )

    def to_model(self) -> TicketUserModel:
        """Convert this row to a [TicketUserModel][]{ data-preview } via the joined user row.

        Returns:
            TicketUserModel: The converted common user model.
        """
        return self.user.to_model()
