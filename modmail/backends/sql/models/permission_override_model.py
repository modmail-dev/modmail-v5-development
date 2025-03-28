"""SQLAlchemy model for command-specific permission overrides.

This module defines the database model for storing command-specific
permission overrides for users and roles. Each override is associated with
a permission group and specifies whether a specific command is allowed
or denied for that group.
"""

from __future__ import annotations

from sqlalchemy import ForeignKeyConstraint, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from modmail.enum import PermissionOverrideValue, ProfileType

from .base import SQLBase

__all__ = ["SQLPermissionOverrideTable"]


class SQLPermissionOverrideTable(SQLBase):
    """SQL model representing command-specific permission overrides.

    This model stores information about permission overrides for specific commands,
    allowing for fine-grained control over who can use which commands regardless of
    their general access level.

    Attributes:
        bot_id: The ID of the bot these permission overrides belong to.
        profile_id: The ID of the user or role this override applies to.
        profile_type: Whether this override applies to a user or role.
        command_name: The name of the command this override applies to (max 256 characters).
        override_value: Whether the command is allowed or denied for this profile.
    """

    __tablename__ = "permission_override"

    bot_id: Mapped[int]
    profile_id: Mapped[int]
    profile_type: Mapped[ProfileType]
    command_name: Mapped[str] = mapped_column(String(256))
    override_value: Mapped[PermissionOverrideValue]

    __table_args__ = (
        PrimaryKeyConstraint(
            "bot_id", "profile_id", "profile_type", "command_name", name="pk_permission_override"
        ),
        ForeignKeyConstraint(
            ["bot_id", "profile_id", "profile_type"],
            ["profile.bot_id", "profile.profile_id", "profile.profile_type"],
            name="fk_permission_override_profile",
            ondelete="CASCADE",
        ),
    )
