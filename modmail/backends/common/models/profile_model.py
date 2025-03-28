"""Provides the Profile data model for managing user profiles.

This module includes configuration for Pydantic-based data parsing and validation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from modmail.enum import AccessLevel, PermissionOverrideValue, ProfileType

__all__ = ["Profile"]


class Profile(BaseModel):
    """Profile data model.

    Attributes:
        bot_id: Bot identifier.
        profile_id: Profile identifier.
        profile_type: The type of the profile.
        access_level: Access level; defaults to None.
        permission_overrides: Command permission overrides mapping command names
            to allow/deny values.
        tag: Optional tag string.
        colour: Color code in hex-integer format (e.g., 0xffffff for white).
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    profile_id: int
    profile_type: ProfileType
    access_level: AccessLevel | None = None

    permission_overrides: dict[str, PermissionOverrideValue] = {}  # format: {command_name: allow/deny, ...}

    tag: str | None = None
    colour: int | None = None  # The color code in hex-integer format 0xffffff = white
