"""Common Pydantic model for bot settings."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from modmail.enum import StatusType

from .activity_model import ActivityModel

__all__ = ["SettingsModel"]


class SettingsModel(BaseModel):
    """Common immutable model for bot settings.

    All fields except [`bot_id`][] are optional. `None` means the value has
    never been set (e.g. `last_ran_version=None` on first run).
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    """Discord application ID of the bot these settings belong to."""
    last_ran_version: str | None = None
    """Bot version string from the last startup, e.g. `"v1.2.3"` (`None` on first run)."""
    last_ran_locale: str | None = None
    """BCP-47 locale code active on the previous run, e.g. `"en"` (`None` on first run)."""
    last_slash_synced_version: str | None = None
    """Bot version when slash commands were last synced to Discord (`None` if never synced)."""
    last_slash_minimum_permission_int: int | None = None
    """Default member permission integer from the last slash-command sync (`None` if never synced)."""
    main_category_or_forum_id: int | None = None
    """Discord category or forum channel ID where new ticket channels are created (`None` if unset)."""
    fallback_category_id: int | None = None
    """Discord category ID used when the main category is full or unavailable (`None` if unset)."""
    log_channel_id: int | None = None
    """Discord channel ID where closed-ticket summaries are posted (`None` if unset)."""
    storage_channel_id: int | None = None
    """Discord channel ID used for internal file storage (`None` if unset)."""
    status: StatusType | None = None
    """Bot presence status shown in Discord as a [StatusType][]{ data-preview } (`None` if unset)."""
    activity: ActivityModel | None = None
    """Bot activity shown in Discord as an [ActivityModel][]{ data-preview } (`None` if unset)."""
