"""SQLAlchemy model for the ticket DM message table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TABLE_OPTS, Snowflake, SQLBase
from .ticket_user_model import SQLTicketUserTable

if TYPE_CHECKING:
    from .ticket_message_model import SQLTicketMessageTable  # noqa: TC004

__all__ = ["SQLTicketDMMessageTable"]


class SQLTicketDMMessageTable(SQLBase):
    """SQL model for the ticket DM message table.

    Each row records one DM delivery of a staff reply to a recipient.

    **Primary key:** [`message_id`][]
    """

    __tablename__ = "ticket_dm_message"

    message_id: Mapped[Snowflake] = mapped_column(primary_key=True)
    """Discord message ID in the recipient's DM channel."""
    ticket_message_ref_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_message.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    """Row ID of the parent [SQLTicketMessageTable][]{ data-preview }
    (distinct from [`message_id`][]).
    """
    ticket_message: Mapped[SQLTicketMessageTable] = relationship(back_populates="dm_messages", lazy="raise_on_sql")
    """[SQLTicketMessageTable][]{ data-preview } this DM delivery belongs to."""
    recipient_id: Mapped[Snowflake] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    """Discord snowflake ID of the user who received the DM."""
    recipient: Mapped[SQLTicketUserTable] = relationship(lazy="joined")
    """[SQLTicketUserTable][]{ data-preview } for the DM recipient."""

    __table_args__ = (
        UniqueConstraint("ticket_message_ref_id", "recipient_id", name="uq_ticket_dm_message"),
        TABLE_OPTS,
    )
