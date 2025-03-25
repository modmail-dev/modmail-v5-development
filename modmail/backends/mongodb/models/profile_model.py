"""
modmail.backends.mongodb.models.profile_model
=============================================
This module defines the MongoDBProfileDocument, which represents a permission group in the MongoDB database.
The model includes fields for bot ID, group ID, group type, permission level, and command overrides.
"""

from __future__ import annotations

from beanie import Document
from pymongo import ASCENDING, IndexModel

from modmail.enum import AccessLevel, PermissionOverrideValue, ProfileType

__all__ = ["MongoDBProfileDocument"]


class MongoDBProfileDocument(Document):
    bot_id: int
    profile_id: int
    profile_type: ProfileType
    access_level: AccessLevel | None = None

    permission_overrides: dict[str, PermissionOverrideValue] = {}  # format: {command_name: allow/deny, ...}

    tag: str | None = None
    colour: int | None = None

    class Settings:
        name = "Profile"
        validate_on_save = True
        indexes = [
            IndexModel(
                [("bot_id", ASCENDING), ("profile_id", ASCENDING), ("profile_type", ASCENDING)],
                unique=True,
                name="profile_unique",
            )
        ]
