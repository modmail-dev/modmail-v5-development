"""
modmail.backends.common.models.permission_group_model
=====================================================
This module defines the model for permission groups.
It provides a structure for representing permission groups with their associated levels.
I.e. user/role <-> permission level
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from modmail.enum import PermissionGroupType, PermissionLevel, PermissionOverrideType

__all__ = ["PermissionGroup"]


class PermissionGroup(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    group_id: int
    group_type: PermissionGroupType
    level: PermissionLevel | None = None

    overrides: dict[str, PermissionOverrideType] = {}  # format: {command_name: allow/deny, ...}

    # tag: str | None = None
    # colour: str | None = None
