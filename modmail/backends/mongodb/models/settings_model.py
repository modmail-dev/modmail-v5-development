"""Defines the MongoDB settings models.

This module includes models for activity configurations and various settings
used by the bot, stored in the MongoDB backend.
"""

from __future__ import annotations

from typing import Annotated

from beanie import Document, Indexed  # pyright: ignore [reportUnknownVariableType]  # beanie is not fully typed
from pydantic import BaseModel

from modmail.enum import ActivityType, StatusType

__all__ = [
    "MongoDBActivityModel",
    "MongoDBSettingsDocument",
]


class MongoDBActivityModel(BaseModel):
    """Represents an activity configuration for the bot.

    This model defines what activity the bot displays in its status.

    Attributes:
        type: The type of the activity (playing, listening, etc.).
        name: The display name of the activity.
        url: The URL for streaming activity type. Optional for other activity types.
    """

    type: ActivityType
    name: str
    url: str | None = None  # url for streaming activity, 'None' not enforced for other types


class MongoDBSettingsDocument(Document):
    """Represents a settings document in MongoDB.

    Stores general configuration settings for the bot including version information,
    category IDs, and activity settings.

    Attributes:
        bot_id: The unique identifier of the bot.
        last_ran_version: The version when the bot last ran. None indicates first run.
        last_ran_locale: The locale setting used during the last run.
        last_slash_synced_version: The version when slash commands were last synchronized.
        last_slash_minimum_permission_int: The minimum permission integer required for using slash commands.
        main_category_or_forum_id: The ID of the main category or forum for organizing channels.
        fallback_category_id: The ID of the fallback category used when main is unavailable.
        log_channel_id: The ID of the log channel.
        storage_channel_id: The ID of the storage channel.
        status: The bot's status.
        activity: The bot's activity.
    """

    bot_id: Annotated[int, Indexed(unique=True)]  # the bot ID
    last_ran_version: str | None = None  # the last version the bot was run on, None = first run
    last_ran_locale: str | None = None  # the last locale the bot was run on
    last_slash_synced_version: str | None = None  # the last version the slash commands were synced on
    last_slash_minimum_permission_int: int | None = None  # the last minimum permission int for slash commands
    main_category_or_forum_id: int | None = None
    fallback_category_id: int | None = None
    log_channel_id: int | None = None
    storage_channel_id: int | None = None
    status: StatusType | None = None
    activity: MongoDBActivityModel | None = None

    class Settings:
        """Settings for the MongoDB document."""

        name = "Settings"
        validate_on_save = True
