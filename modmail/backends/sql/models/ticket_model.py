"""SQLAlchemy model for the ticket table."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.backends.common import TicketModel
from modmail.enum import TicketStatus

from .base import TABLE_OPTS, Snowflake, SQLBase
from .ticket_recipient_model import SQLTicketRecipientTable
from .ticket_user_model import SQLTicketUserTable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["SQLTicketTable"]


class SQLTicketTable(SQLBase):
    """SQL model for the ticket table.

    A unique constraint on ([`bot_id`][], [`channel_id`][]) enforces one ticket per Discord channel.
    Recipients are stored in a separate [SQLTicketRecipientTable][]{ data-preview } table.

    **Primary keys:** [`bot_id`][], [`key`][]
    """

    __tablename__ = "ticket"

    bot_id: Mapped[Snowflake]
    """Discord application ID of the bot that owns this ticket."""
    key: Mapped[str] = mapped_column(String(12))
    """Random 12-character alphanumeric ticket identifier."""

    recipients: Mapped[list[SQLTicketRecipientTable]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )
    """Non-staff users who are parties to this ticket, as
    [SQLTicketRecipientTable][]{ data-preview } rows.
    """
    channel_id: Mapped[Snowflake]
    """Discord channel or forum-thread ID where staff interact."""

    created_at: Mapped[datetime.datetime]
    """UTC-aware timestamp when the ticket was opened."""
    created_by_id: Mapped[Snowflake] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    """Discord snowflake ID of the user who opened the ticket."""
    created_by: Mapped[SQLTicketUserTable] = relationship(foreign_keys=[created_by_id], lazy="joined")
    """[SQLTicketUserTable][]{ data-preview } who opened the ticket."""

    closed_at: Mapped[datetime.datetime | None]
    """UTC-aware timestamp when the ticket was closed (`None` if [`closed_by`][] is unset)."""
    closed_by_id: Mapped[Snowflake | None] = mapped_column(
        ForeignKey("ticket_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    """Discord snowflake ID of the user who closed the ticket (`None` if [`closed_at`][] is unset)."""
    closed_by: Mapped[SQLTicketUserTable | None] = relationship(foreign_keys=[closed_by_id], lazy="joined")
    """[SQLTicketUserTable][]{ data-preview } who closed the ticket
    (`None` if [`closed_at`][] is unset).
    """

    log_channel_message_id: Mapped[Snowflake | None]
    """Summary message ID posted to the log channel on closure (`None` if not yet posted)."""

    status: Mapped[TicketStatus]
    """Current lifecycle state as a [TicketStatus][]{ data-preview }."""
    title: Mapped[str | None] = mapped_column(String(1024))
    """Human-readable title for the ticket (`None` if unset)."""
    nsfw: Mapped[bool] = mapped_column(default=False)
    """Whether the ticket channel is marked as age-restricted in Discord."""

    __table_args__ = (
        PrimaryKeyConstraint("bot_id", "key"),
        UniqueConstraint("bot_id", "channel_id", name="uq_ticket_channel"),
        TABLE_OPTS,
    )

    def to_model(self) -> TicketModel:
        """Convert this row to a [TicketModel][]{ data-preview }.

        Returns:
            TicketModel: The converted common ticket model.
        """
        return TicketModel(
            bot_id=self.bot_id,
            key=self.key,
            recipients=[r.to_model() for r in self.recipients],
            channel_id=self.channel_id,
            created_at=self.created_at,
            created_by=self.created_by.to_model(),
            status=self.status,
            closed_by=self.closed_by.to_model() if self.closed_by else None,
            closed_at=self.closed_at,
            log_channel_message_id=self.log_channel_message_id,
            title=self.title,
            nsfw=self.nsfw,
        )

    @classmethod
    async def put_model(cls, model: TicketModel, session: AsyncSession) -> None:
        """Insert a new ticket and its recipient records within the provided session.

        Note:
            Must be called inside an active `session.begin()` block. The caller is
            responsible for committing or rolling back the transaction.

        Args:
            model: The ticket to persist.
            session: An open [AsyncSession][] with an active transaction.

        Raises:
            RuntimeError: If called outside an active `session.begin()` block.
            sqlalchemy.exc.SQLAlchemyError: If an unexpected database error occurs.
        """
        if not session.in_transaction():
            raise RuntimeError("put_model must be called inside an active session.begin() block")

        await SQLTicketUserTable.put_many(
            model.created_by,
            *model.recipients,
            *([model.closed_by] if model.closed_by else []),
            session=session,
        )

        session.add(
            cls(
                bot_id=model.bot_id,
                key=model.key,
                channel_id=model.channel_id,
                created_at=model.created_at,
                created_by_id=model.created_by.user_id,
                closed_at=model.closed_at,
                closed_by_id=model.closed_by.user_id if model.closed_by else None,
                log_channel_message_id=model.log_channel_message_id,
                status=model.status,
                title=model.title,
                nsfw=model.nsfw,
                recipients=[
                    SQLTicketRecipientTable(
                        bot_id=model.bot_id,
                        ticket_key=model.key,
                        user_id=recipient.user_id,
                    )
                    for recipient in model.recipients
                ],
            )
        )
