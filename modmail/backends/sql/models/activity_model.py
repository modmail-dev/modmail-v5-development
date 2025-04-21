"""SQLAlchemy model for the activity table.

This module defines the database model for storing bot activity information,
such as the activity type, name, and URL.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from modmail.enum import ActivityType

from .base import SQLBase

__all__ = ["SQLActivityTable"]


class SQLActivityTable(SQLBase):
    """SQL model representing bot activity configuration.

    This model stores information about a bot's Discord activity status,
    including the activity type, name, and optional URL.

    Attributes:
        bot_id: The ID of the bot this activity belongs to, foreign key to settings table.
        type: The type of activity (playing, streaming, watching, etc.).
        name: The displayed activity text (max 128 characters).
        url: Optional URL for the activity, primarily used for streaming status (max 2048 characters).
    """

    __tablename__ = "activity"

    bot_id: Mapped[int] = mapped_column(
        ForeignKey("settings.bot_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True
    )
    type: Mapped[ActivityType]
    name: Mapped[str] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(2048))
