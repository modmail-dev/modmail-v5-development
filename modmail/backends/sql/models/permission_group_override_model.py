"""
modmail.backends.sql.models.permission_group_override_model
===========================================================
This module defines the SQLPermissionGroupOverrideTable class which stores command-specific
permission overrides for users and roles. Each override is associated with a permission group
and specifies whether a specific command is allowed or denied for that group.
"""

from __future__ import annotations

from sqlalchemy import ForeignKeyConstraint, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from modmail.enum import PermissionGroupType, PermissionOverrideType

from .base import SQLBase

__all__ = ["SQLPermissionGroupOverrideTable"]


class SQLPermissionGroupOverrideTable(SQLBase):
    __tablename__ = "permission_group_override"

    bot_id: Mapped[int]
    group_id: Mapped[int]
    group_type: Mapped[PermissionGroupType]
    command_name: Mapped[str] = mapped_column(String(256))
    override_value: Mapped[PermissionOverrideType]

    __table_args__ = (
        PrimaryKeyConstraint(
            "bot_id", "group_id", "group_type", "command_name", name="pk_permission_group_override"
        ),
        ForeignKeyConstraint(
            ["bot_id", "group_id", "group_type"],
            ["permission_group.bot_id", "permission_group.group_id", "permission_group.group_type"],
            name="fk_permission_group_override_permission_group",
            ondelete="CASCADE",
        ),
    )
