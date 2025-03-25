"""
modmail.backends.sql.models.profile_model
=========================================
This module defines the SQLProfileTable class which stores permission levels
for users and roles, along with their command-specific permission overrides.
"""

from __future__ import annotations

from sqlalchemy import PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.enum import AccessLevel, ProfileType

from .base import SQLBase
from .permission_override_model import SQLPermissionOverrideTable

__all__ = ["SQLProfileTable"]


class SQLProfileTable(SQLBase):
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
