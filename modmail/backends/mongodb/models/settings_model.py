"""
modmail.backends.mongodb.models.settings_model
==============================================
This module defines the MongoDB model for the settings collection.
"""

from __future__ import annotations

import enum
from typing import Annotated

from beanie import Indexed  # type: ignore[reportUnknownVariableType]  # beanie is not fully typed
from beanie import Document
from pydantic import BaseModel

__all__ = [
    "Settings",
    "Activity",
    "ActivityType",
    "StatusType",
]


class StatusType(enum.Enum):
    online = 0
    idle = 1
    dnd = 2
    offline = 3


class ActivityType(enum.Enum):
    playing = 0
    streaming = 1
    listening = 2
    watching = 3
    custom = 4
    competing = 5


class Activity(BaseModel):
    type: ActivityType
    name: str
    url: str | None = None  # url for streaming activity, 'None' not enforced for other types


class Settings(Document):
    bot_id: Annotated[int, Indexed(unique=True)]  # the bot ID
    last_ran_version: str | None = None  # the last version the bot was run on, None = first run
    main_category_id: int | None = None
    fallback_category_id: int | None = None
    status: StatusType | None = None
    activity: Activity | None = None

    class Settings:
        validate_on_save = True
