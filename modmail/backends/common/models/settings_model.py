"""
modmail.backends.common.models.settings_model
==============================================
This module defines a uniform model for exporting settings.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict

from .activity_model import Activity

__all__ = [
    "Settings",
    "StatusType",
]


class StatusType(enum.Enum):
    online = 0
    idle = 1
    dnd = 2
    offline = 3

    def __str__(self) -> str:
        """
        Returns a string representation of the status.
        """
        match self:
            case StatusType.online:
                return "Online"
            case StatusType.idle:
                return "Idle"
            case StatusType.dnd:
                return "Do Not Disturb (dnd)"
            case StatusType.offline:
                return "Offline"


class Settings(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    last_ran_version: str | None  # the last version the bot was run on, None = first run
    main_category_id: int | None
    fallback_category_id: int | None
    status: StatusType | None
    activity: Activity | None
