"""
modmail.backends.common.models.settings_model
==============================================
This module defines a uniform model for exporting settings.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from modmail.enum import StatusType

from .activity_model import Activity
from .permission_group_model import PermissionGroup
from .permission_override_model import PermissionOverride

__all__ = [
    "Settings",
]


class Settings(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    last_ran_version: str | None  # the last version the bot was run on, None = first run
    slash_last_synced_version: str | None  # the last version the slash commands were synced on
    main_category_id: int | None
    fallback_category_id: int | None
    status: StatusType | None
    activity: Activity | None

    permission_groups: list[PermissionGroup] = []
    # format: command_name: override_entry
    permission_overrides: dict[str, PermissionOverride] = {}
