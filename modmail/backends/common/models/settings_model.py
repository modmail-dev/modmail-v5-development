"""
modmail.backends.common.models.settings_model
==============================================
This module defines a uniform model for exporting settings.
"""

from __future__ import annotations

import enum

from discord import app_commands
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

    @property
    def official_name(self) -> app_commands.locale_str:
        """
        Returns a locale_str of the localized name of the status.
        """
        # noinspection PyProtectedMember
        from modmail.core import _

        match self:
            case StatusType.online:
                return _("model-status-online-name")
            case StatusType.idle:
                return _("model-status-idle-name")
            case StatusType.dnd:
                return _("model-status-dnd-name")
            case StatusType.offline:
                return _("model-status-offline-name")

    def __locale_str__(self) -> app_commands.locale_str:
        """
        Returns a locale_str of the localized name of the status.
        """
        # noinspection PyProtectedMember
        from modmail.core import _

        return _(f"model-status-text", status=self.name)


class Settings(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    last_ran_version: str | None  # the last version the bot was run on, None = first run
    slash_last_synced_version: str | None  # the last version the slash commands were synced on
    main_category_id: int | None
    fallback_category_id: int | None
    status: StatusType | None
    activity: Activity | None
