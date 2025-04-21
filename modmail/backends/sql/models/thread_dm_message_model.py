"""Thread Direct Message SQL Model.

This module defines the SQLThreadDMMessageTable class, which represents
the thread direct message table in the database.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import SQLBase
from .thread_message_model import SQLThreadMessageTable
from .thread_user_model import SQLThreadUserTable

__all__ = ["SQLThreadDMMessageTable"]


class SQLThreadDMMessageTable(SQLBase):
    """SQL model representing a direct message in a thread.

    This model stores information about a direct message, including its ID,
    the associated thread message, the recipient user, and other metadata.

    Attributes:
        message_id: The unique identifier of the direct message.
        thread_message_ref_id: The ID of the associated thread message row.
        thread_message: The thread message associated with this direct message.
        recipient_id: The ID of the recipient user.
        recipient: The recipient user of this direct message.
    """

    __tablename__ = "thread_dm_message"

    message_id: Mapped[int] = mapped_column(primary_key=True)
    thread_message_ref_id: Mapped[int] = mapped_column(
        ForeignKey("thread_message.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    thread_message: Mapped[SQLThreadMessageTable] = relationship(back_populates="dm_messages", lazy="joined")
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("thread_user.user_id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    recipient: Mapped[SQLThreadUserTable] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("message_id", "thread_message_ref_id", name="uq_thread_dm_message"),)
