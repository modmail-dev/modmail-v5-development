"""SQLAlchemy model for the bot activity table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from modmail.enum import ActivityType

from .base import Snowflake, SQLBase

if TYPE_CHECKING:
    from modmail.backends.common import ActivityModel

__all__ = ["SQLActivityTable"]


class SQLActivityTable(SQLBase):
    """SQL model for the bot activity table.

    [`url`][] is only meaningful when [`type`][] is [`ActivityType.streaming`][].

    **Primary key:** [`bot_id`][]
    """

    __tablename__ = "activity"

    bot_id: Mapped[Snowflake] = mapped_column(
        ForeignKey("settings.bot_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True
    )
    """Discord application ID of the bot this activity belongs to."""
    type: Mapped[ActivityType]
    """[ActivityType][]{ data-preview } controlling how the activity appears in Discord."""
    name: Mapped[str] = mapped_column(String(128))
    """Display name of the activity shown in the bot's status."""
    url: Mapped[str | None] = mapped_column(String(2048))
    """Stream URL (`None` if [`type`][] is not [`ActivityType.streaming`][])."""

    @classmethod
    def from_model(cls, model: ActivityModel, *, bot_id: int) -> SQLActivityTable:
        """Construct a table from an [ActivityModel][]{ data-preview }.

        Args:
            model: The activity model to convert.
            bot_id: Discord application ID of the bot.

        Returns:
            SQLActivityTable: An unsaved row ready to merge into a session.
        """
        return cls(**model.model_dump(exclude={"bot_id"}), bot_id=bot_id)
