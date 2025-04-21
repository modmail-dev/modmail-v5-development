"""SQLAlchemy model for thread users.

This module defines the SQLThreadUserTable class, which represents
the thread user table in the database.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.enum import ThreadMessageType

from .base import SQLBase
from .thread_user_model import SQLThreadUserTable

if TYPE_CHECKING:
    from .thread_dm_message_model import SQLThreadDMMessageTable

__all__ = ["SQLThreadMessageTable"]


class SQLThreadMessageTable(SQLBase):
    """SQL model representing a message in a thread.

    This model stores information about a message, including its ID, the
    associated thread, the author, content, timestamps, and other metadata.

    Attributes:
        id: A surrogate key for this table.
        bot_id: The unique identifier of the bot.
        thread_key: The unique key for the thread.
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

    __tablename__ = "thread_message"

    # Not using `message_id` as primary key because multiple bots may have the same message ID.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_id: Mapped[int]
    thread_key: Mapped[str] = mapped_column(String(12))

    message_id: Mapped[int]
    dm_messages: Mapped[list[SQLThreadDMMessageTable]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="thread_message",
        lazy="selectin",
    )

    author_id: Mapped[int] = mapped_column(
        ForeignKey("thread_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    author: Mapped[SQLThreadUserTable] = relationship(foreign_keys=[author_id], lazy="joined")

    content: Mapped[str] = mapped_column(String(4096))
    created_at: Mapped[datetime]

    edited_at: Mapped[datetime | None]
    edited_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("thread_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    edited_by: Mapped[SQLThreadUserTable | None] = relationship(foreign_keys=[edited_by_id], lazy="joined")

    deleted_at: Mapped[datetime | None]
    deleted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("thread_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    deleted_by: Mapped[SQLThreadUserTable | None] = relationship(foreign_keys=[deleted_by_id], lazy="joined")

    type: Mapped[ThreadMessageType]

    __table_args__ = (
        UniqueConstraint("bot_id", "thread_key", "message_id", name="uq_thread_message"),
        ForeignKeyConstraint(
            ["bot_id", "thread_key"],
            ["thread.bot_id", "thread.key"],
            name="fk_thread_message_thread",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
    )
