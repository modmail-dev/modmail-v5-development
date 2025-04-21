"""Provides the Settings model for managing bot settings.

This module provides a Pydantic model representing various bot settings.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from modmail.enum import StatusType

from .activity_model import ActivityModel

__all__ = ["SettingsModel"]


class SettingsModel(BaseModel):
    """Settings model for bot configuration.

    Attributes:
        bot_id: Bot identifier.
        last_ran_version: Last version that the bot was run on; None indicates first run.
        last_ran_locale: Last locale used when running the bot.
        last_slash_synced_version: Last version in which slash commands were synced.
        last_slash_minimum_permission_int: Last minimum permission integer for slash commands.
        main_category_id: Main category identifier.
        fallback_category_id: Fallback category identifier.
        log_channel_id: Log channel identifier.
        storage_channel_id: Storage channel identifier.
        status: The bot's status.
        activity: The bot's activity.
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    last_ran_version: str | None = None  # The last version the bot was run on, None = first run
    last_ran_locale: str | None = None  # The last locale the bot was run on
    last_slash_synced_version: str | None = None  # The last version the slash commands were synced on
    last_slash_minimum_permission_int: int | None = None  # The last minimum permission int for slash commands
    main_category_id: int | None = None
    fallback_category_id: int | None = None
    log_channel_id: int | None = None
    storage_channel_id: int | None = None
    status: StatusType | None = None
    activity: ActivityModel | None = None
