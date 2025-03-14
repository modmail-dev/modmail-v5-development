"""
modmail.backends.mongodb.models.settings_model
==============================================
This module defines the MongoDB model for the settings collection.
"""

from __future__ import annotations

from typing import Annotated

from beanie import Indexed  # type: ignore[reportUnknownVariableType]  # beanie is not fully typed
from beanie import Document
from pydantic import BaseModel

from modmail.backends import ActivityType, StatusType

__all__ = [
    "MongoDBSettingsModel",
    "MongoDBActivityModel",
]


class MongoDBActivityModel(BaseModel):
    type: ActivityType
    name: str
    url: str | None = None  # url for streaming activity, 'None' not enforced for other types


class MongoDBSettingsModel(Document):
    bot_id: Annotated[int, Indexed(unique=True)]  # the bot ID
    last_ran_version: str | None = None  # the last version the bot was run on, None = first run
    main_category_id: int | None = None
    fallback_category_id: int | None = None
    status: StatusType | None = None
    activity: MongoDBActivityModel | None = None

    class Settings:
        name = "settings"
        validate_on_save = True
