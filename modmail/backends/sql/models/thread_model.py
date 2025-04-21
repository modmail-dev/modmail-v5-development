"""SQLAlchemy model for thread users.

This module defines the SQLThreadUserTable class, which represents
the thread user table in the database.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.backends.common import ThreadModel
from modmail.enum import ThreadStatus

from .base import SQLBase
from .thread_recipient_model import SQLThreadRecipientTable
from .thread_user_model import SQLThreadUserTable

__all__ = ["SQLThreadTable"]


class SQLThreadTable(SQLBase):
    """SQL model representing a thread.

    This model stores information about a thread, including its ID, key,
    participants, channel ID, creation time, status, and other metadata.

    Attributes:
        bot_id: The unique identifier of the bot.
        key: The unique key for the thread.
        recipients: List of users involved in the thread.
        channel_id: The ID of the channel associated with the thread.
        created_at: The timestamp when the thread was created.
        created_by: The user who created the thread.
        status: The current status of the thread (open, closed, etc.).
        closed_by: The user who closed the thread (if applicable).
        closed_at: The timestamp when the thread was closed (if applicable).
        title: An optional title for the thread.
        nsfw: A boolean indicating if the thread is NSFW (not safe for work).
    """

    __tablename__ = "thread"

    bot_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(12), primary_key=True)

    recipients: Mapped[list[SQLThreadRecipientTable]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )
    channel_id: Mapped[int]

    created_at: Mapped[datetime]
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("thread_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    created_by: Mapped[SQLThreadUserTable] = relationship(foreign_keys=[created_by_id], lazy="joined")

    closed_at: Mapped[datetime | None]
    closed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("thread_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    closed_by: Mapped[SQLThreadUserTable | None] = relationship(foreign_keys=[closed_by_id], lazy="joined")

    status: Mapped[ThreadStatus]
    title: Mapped[str | None]
    nsfw: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (UniqueConstraint("bot_id", "channel_id", name="uq_thread_channel"),)

    async def get_model(self) -> ThreadModel:
        """Get the thread model associated with this thread.

        Returns:
            The converted ThreadModel.
        """
        recipients = await asyncio.gather(*[recipient.get_model() for recipient in self.recipients])
        created_by = await self.created_by.get_model()
        closed_by = await self.closed_by.get_model() if self.closed_by else None

        return ThreadModel(
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
