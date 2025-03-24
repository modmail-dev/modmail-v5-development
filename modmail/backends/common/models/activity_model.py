"""
modmail.backends.common.models.activity_model
==============================================
This module defines the Pydantic models for Activity and enumerated types for ActivityType.
"""

from __future__ import annotations

from discord import app_commands
from pydantic import BaseModel, ConfigDict

from modmail.enum import ActivityType

__all__ = [
    "Activity",
]


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
            "ftl-model-activity-text", activity_type=self.type, activity_name=self.name, activity_url=self.url
        )
