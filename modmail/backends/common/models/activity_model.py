"""
modmail.backends.common.models.activity_model
==============================================
This module defines the Pydantic models for Activity and enumerated types for ActivityType.
"""

from __future__ import annotations

import enum

from discord import app_commands
from pydantic import BaseModel, ConfigDict

__all__ = [
    "Activity",
    "ActivityType",
]


class ActivityType(enum.Enum):
    playing = 0
    streaming = 1
    listening = 2
    watching = 3
    custom = 4
    competing = 5

    @property
    def official_name(self) -> app_commands.locale_str:
        """
        Returns a locale_str representation of the Discord prefix for the activity type.

        e.g. "playing" -> "playing", "listening" -> "listening to", etc.
        """
        # noinspection PyProtectedMember
        from modmail.core import _

        match self:
            case ActivityType.playing:
                return _("model-activity-playing-name")
            case ActivityType.streaming:
                return _("model-activity-streaming-name")
            case ActivityType.listening:
                return _("model-activity-listening-name")
            case ActivityType.watching:
                return _("model-activity-watching-name")
            case ActivityType.competing:
                return _("model-activity-competing-name")
            case ActivityType.custom:
                return _("flt-blank")


class Activity(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    type: ActivityType
    name: str
    url: str | None = None  # url for streaming activity, 'None' not enforced for other types

    def __str__(self) -> str:
        """
        Returns a string representation of the activity.
        """
        match self.type:
            case ActivityType.playing:
                return f"Playing {self.name}"
            case ActivityType.streaming:
                return f"Streaming {self.name} ({self.url if self.url else 'No URL'})"
            case ActivityType.listening:
                return f"Listening to {self.name}"
            case ActivityType.watching:
                return f"Watching {self.name}"
            case ActivityType.custom:
                return f"{self.name} (custom)"
            case ActivityType.competing:
                return f"Competing in {self.name}"

    def __locale_str__(self) -> app_commands.locale_str:
        """
        Returns a locale_str representation of the activity.
        """
        # noinspection PyProtectedMember
        from modmail.core import _

        return _(
            "model-activity-text", activity_type=self.type.name, activity_name=self.name, activity_url=self.url
        )
