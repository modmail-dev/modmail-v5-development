"""
modmail.backends.common.models.activity_model
==============================================
This module defines the Pydantic models for Activity and enumerated types for ActivityType.
"""

from __future__ import annotations

import enum

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
