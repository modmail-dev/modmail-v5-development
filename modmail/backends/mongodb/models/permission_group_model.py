"""
modmail.backends.mongodb.models.permission_group_model
======================================================
This module defines the MongoDBPermissionGroupModel, which represents a permission group in the MongoDB database.
The model includes fields for bot ID, group ID, group type, permission level, and command overrides.
"""

from __future__ import annotations

from beanie import Document
from pymongo import ASCENDING, IndexModel

from modmail.enum import PermissionGroupType, PermissionLevel, PermissionOverrideType

__all__ = ["MongoDBPermissionGroupDocument"]


class MongoDBPermissionGroupDocument(Document):
    bot_id: int
    group_id: int
    group_type: PermissionGroupType
    level: PermissionLevel | None = None

    overrides: dict[str, PermissionOverrideType] = {}  # format: {command_name: allow/deny, ...}

    class Settings:
        name = "PermissionGroup"
        validate_on_save = True
        indexes = [
            IndexModel(
                [("bot_id", ASCENDING), ("group_id", ASCENDING), ("group_type", ASCENDING)],
                unique=True,
                name="permission_group_unique_group",
            )
        ]
