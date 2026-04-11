"""Common Pydantic model for a bot Discord activity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from modmail.enum import ActivityType

if TYPE_CHECKING:
    from discord import app_commands

__all__ = ["ActivityModel"]


class ActivityModel(BaseModel):
    """Common immutable model for a bot Discord activity.

    [`url`][] is only meaningful for the [`ActivityType.streaming`][] activity type and is not
    validated for other types.
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    type: ActivityType
    """[ActivityType][]{ data-preview } controlling how the activity appears in Discord."""
    name: str
    """Display name of the activity shown in the bot's status."""
    url: str | None = None
    """Stream URL (`None` if [`type`][] is not [`ActivityType.streaming`][])."""

    def __str__(self) -> str:
        """Return a human-readable description of the activity."""
        match self.type:
            case ActivityType.playing:
                return f"Playing {self.name}"
            case ActivityType.streaming:
                return f"Streaming {self.name} ({self.url or 'No URL'})"
            case ActivityType.listening:
                return f"Listening to {self.name}"
            case ActivityType.watching:
                return f"Watching {self.name}"
            case ActivityType.custom:
                return f"{self.name} (custom)"
            case ActivityType.competing:
                return f"Competing in {self.name}"

    def __locale_str__(self) -> app_commands.locale_str:
        """Return the localized string representation of the activity via the Fluent translator."""
        from modmail.core import _

        return _(
            "ftl-model-activity-text", activity_type=self.type, activity_name=self.name, activity_url=self.url
        )
