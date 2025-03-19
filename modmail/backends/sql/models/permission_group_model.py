"""
modmail.backends.sql.models.permission_group_model
==================================================
This module defines the SQLPermissionGroupTable class which stores permission levels
for users and roles, along with their command-specific permission overrides.
"""

from __future__ import annotations

from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, relationship

from modmail.enum import PermissionGroupType, PermissionLevel

from .base import SQLBase
from .permission_group_override_model import SQLPermissionGroupOverrideTable

__all__ = ["SQLPermissionGroupTable"]


class SQLPermissionGroupTable(SQLBase):
    __tablename__ = "permission_group"

    bot_id: Mapped[int]
    group_id: Mapped[int]
    group_type: Mapped[PermissionGroupType]
    level: Mapped[PermissionLevel | None]
    overrides: Mapped[list[SQLPermissionGroupOverrideTable]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, uselist=True, lazy="selectin"
    )
    __table_args__ = (PrimaryKeyConstraint("bot_id", "group_id", "group_type", name="permission_group_pk"),)
