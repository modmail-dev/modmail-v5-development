"""
modmail.backends.common.models.settings_model
==============================================
This module defines a uniform model for exporting settings.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from modmail.enum import StatusType

from .activity_model import Activity

__all__ = [
    "Settings",
]


class Settings(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    last_ran_version: str | None = None  # the last version the bot was run on, None = first run
    last_ran_locale: str | None = None  # the last locale the bot was run on
    last_slash_synced_version: str | None = None  # the last version the slash commands were synced on
    last_slash_minimum_permission_int: int | None = None  # the last minimum permission int for slash commands
    main_category_id: int | None = None
    fallback_category_id: int | None = None
    status: StatusType | None = None
    activity: Activity | None = None
