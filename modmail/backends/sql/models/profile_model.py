"""SQLAlchemy model for permission profiles.

This module defines the database model for storing permission levels
for users and roles, along with their command-specific permission overrides,
tags, and display colors.
"""

from __future__ import annotations

from sqlalchemy import PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.enum import AccessLevel, ProfileType

from .base import SQLBase
from .permission_override_model import SQLPermissionOverrideTable

__all__ = ["SQLProfileTable"]


class SQLProfileTable(SQLBase):
    """SQL model representing user or role permission profiles.

    This model stores permission information for users and roles, including
    their access level, command-specific overrides, and display properties.

    Attributes:
        bot_id: The ID of the bot these permissions apply to.
        profile_id: The ID of the user or role.
        profile_type: Whether this profile belongs to a user or role.
        access_level: The general access level granted to this profile.
        permission_overrides: Command-specific permission overrides for this profile.
        tag: Optional tag attribute (max 128 characters).
        colour: Optional colour attribute.
    """

    __tablename__ = "profile"

    bot_id: Mapped[int]
    profile_id: Mapped[int]
    profile_type: Mapped[ProfileType]
    access_level: Mapped[AccessLevel | None]
    permission_overrides: Mapped[list[SQLPermissionOverrideTable]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, uselist=True, lazy="selectin"
    )
    tag: Mapped[str | None] = mapped_column(String(128))
    colour: Mapped[int | None]

    __table_args__ = (PrimaryKeyConstraint("bot_id", "profile_id", "profile_type", name="profile_pk"),)
