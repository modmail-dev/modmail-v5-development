"""Defines the MongoDB profile document.

This module contains the MongoDBProfileDocument class.
"""

from __future__ import annotations

from beanie import Document
from pymongo import ASCENDING, IndexModel

from modmail.enum import AccessLevel, PermissionOverrideValue, ProfileType

__all__ = ["MongoDBProfileDocument"]


class MongoDBProfileDocument(Document):
    """Represents a MongoDB profile document for a permission group.

    A profile defines permission settings and appearance attributes for different
    user groups within the bot system.

    Attributes:
        bot_id: The unique identifier of the bot.
        profile_id: The unique identifier for the profile.
        profile_type: The type of the profile (user, role).
        access_level: The profile's access level that defines default permissions.
        permission_overrides: Command-specific permission overrides in format
            {command_name: allow/deny, ...}.
        tag: An optional tag.
        colour: An optional colour value.
    """

    bot_id: int
    profile_id: int
    profile_type: ProfileType
    access_level: AccessLevel | None = None

    permission_overrides: dict[str, PermissionOverrideValue] = {}  # format: {command_name: allow/deny, ...}

    tag: str | None = None
    colour: int | None = None

    class Settings:
        """Settings for the MongoDB profile document."""

        name = "Profile"
        validate_on_save = True
        indexes = [
            IndexModel(
                [("bot_id", ASCENDING), ("profile_id", ASCENDING), ("profile_type", ASCENDING)],
                unique=True,
                name="profile_unique",
            )
        ]
