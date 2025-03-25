"""
modmail.backends.common.models.profile_model
============================================
This module provides the Profile data model for managing user profiles.
It includes configuration for pydantic-based data parsing and validation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from modmail.enum import AccessLevel, PermissionOverrideValue, ProfileType

__all__ = ["Profile"]


class Profile(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    profile_id: int
    profile_type: ProfileType
    access_level: AccessLevel | None = None

    permission_overrides: dict[str, PermissionOverrideValue] = {}  # format: {command_name: allow/deny, ...}

    tag: str | None = None
    colour: int | None = None  # The color code in hex-integer format 0xffffff = white
