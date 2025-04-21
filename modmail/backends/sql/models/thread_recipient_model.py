"""Represents a recipient in a thread.

This module defines the SQLThreadRecipientTable class, which represents
the thread recipient table in the database. It includes information about
the recipient user, the associated thread, and other metadata.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.backends.common import ThreadUserModel

from .base import SQLBase
from .thread_user_model import SQLThreadUserTable

__all__ = ["SQLThreadRecipientTable"]


class SQLThreadRecipientTable(SQLBase):
    """SQL model representing a recipient in a thread.

    This model stores information about a recipient user in a thread,
    including their user ID, the associated thread, and other metadata.

    Attributes:
        id: A surrogate key for this table.
        bot_id: The unique identifier of the bot.
        thread_key: The unique key for the thread.
        user_id: The ID of the recipient user.
        user: The recipient user associated with this thread.
    """

    __tablename__ = "thread_recipient"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_id: Mapped[int]
    thread_key: Mapped[str] = mapped_column(String(12))
    user_id: Mapped[int] = mapped_column(
        ForeignKey("thread_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    user: Mapped[SQLThreadUserTable] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("bot_id", "thread_key", "user_id", name="uq_thread_recipient"),
        ForeignKeyConstraint(
            ["bot_id", "thread_key"],
            ["thread.bot_id", "thread.key"],
            name="fk_thread_recipient_thread",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
    )

    async def get_model(self) -> ThreadUserModel:
        """Get the thread user model associated with this recipient.

        Returns:
            ThreadUserModel: The thread user model.
        """
        return await self.user.get_model()
