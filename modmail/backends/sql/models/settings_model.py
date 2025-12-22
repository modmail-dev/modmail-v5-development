"""SQLAlchemy model for bot settings.

This module defines the database model for storing global bot configuration
settings, including version information, category IDs, and activity status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.enum import StatusType

from .base import SQLBase

if TYPE_CHECKING:
    from .activity_model import SQLActivityTable

__all__ = ["SQLSettingsTable"]


class SQLSettingsTable(SQLBase):
    """SQL model representing global bot settings.

    This model stores configuration settings for the bot, including version information,
    Discord category IDs for ticket management, status information, and activity details.

    Attributes:
        bot_id: The unique identifier for the bot.
        last_ran_version: The version of the bot when it was last run (max 32 characters).
        last_ran_locale: The locale setting when the bot was last run (max 8 characters).
        last_slash_synced_version: The version when slash commands were last synchronized (max 32 characters).
        last_slash_minimum_permission_int: The minimum permission level required for slash commands.
        main_category_or_forum_id: The Discord category or forum ID where new tickets are created.
        fallback_category_id: The backup Discord category ID for when the main category is full.
        log_channel_id: The Discord channel ID for the log channel.
        storage_channel_id: The Discord channel ID for the storage channel.
        status: The bot's current status type.
        activity: The bot's current activity configuration.
    """

    __tablename__ = "settings"

    bot_id: Mapped[int] = mapped_column(primary_key=True)
    last_ran_version: Mapped[str | None] = mapped_column(String(32))
    last_ran_locale: Mapped[str | None] = mapped_column(String(8))
    last_slash_synced_version: Mapped[str | None] = mapped_column(String(32))
    last_slash_minimum_permission_int: Mapped[int | None]
    main_category_or_forum_id: Mapped[int | None]
    fallback_category_id: Mapped[int | None]
    log_channel_id: Mapped[int | None]
    storage_channel_id: Mapped[int | None]
    status: Mapped[StatusType | None]
    activity: Mapped[SQLActivityTable | None] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, single_parent=True, lazy="joined"
    )
