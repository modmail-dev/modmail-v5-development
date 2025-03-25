"""
modmail.backends.sql.models.permission_override_model
===========================================================
This module defines the SQLPermissionOverrideTable class which stores command-specific
permission overrides for users and roles. Each override is associated with a permission group
and specifies whether a specific command is allowed or denied for that group.
"""

from __future__ import annotations

from sqlalchemy import ForeignKeyConstraint, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from modmail.enum import PermissionOverrideValue, ProfileType

from .base import SQLBase

__all__ = ["SQLPermissionOverrideTable"]


class SQLPermissionOverrideTable(SQLBase):
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
