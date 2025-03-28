"""Defines the Pydantic model for Activity.

This module provides a model for representing Discord activities.
"""

from __future__ import annotations

from discord import app_commands
from pydantic import BaseModel, ConfigDict

from modmail.enum import ActivityType

__all__ = [
    "Activity",
]


class Activity(BaseModel):
    """Represents a Discord activity.

    Attributes:
        type: The type of activity.
        name: The activity name.
        url: The URL for streaming activities. Defaults to None.
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    type: ActivityType
    name: str
    url: str | None = None  # URL for streaming activity; not enforced for other types

    def __str__(self) -> str:
        """Returns a string representation of the activity.

        Returns:
            A description of the activity.
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
        """Returns a localized string representation of the activity.

        Returns:
            The locale-specific string.
        """
        from modmail.core import _

        return _(
            "ftl-model-activity-text", activity_type=self.type, activity_name=self.name, activity_url=self.url
        )
