"""
modmail.backends.mongodb.models.settings_model
==============================================
This module defines the MongoDB model for the settings collection.
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
    type: ActivityType
    name: str
    url: str | None = None  # url for streaming activity, 'None' not enforced for other types


class MongoDBSettingsDocument(Document):
    bot_id: Annotated[int, Indexed(unique=True)]  # the bot ID
    last_ran_version: str | None = None  # the last version the bot was run on, None = first run
    last_ran_locale: str | None = None  # the last locale the bot was run on
    last_slash_synced_version: str | None = None  # the last version the slash commands were synced on
    last_slash_minimum_permission_int: int | None = None  # the last minimum permission int for slash commands
    main_category_id: int | None = None
    fallback_category_id: int | None = None
    status: StatusType | None = None
    activity: MongoDBActivityModel | None = None

    class Settings:
        name = "Settings"
        validate_on_save = True
