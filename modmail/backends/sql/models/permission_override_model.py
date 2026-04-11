"""SQLAlchemy model for the command-specific permission override table."""

from __future__ import annotations

from sqlalchemy import ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from modmail.enum import PermissionOverrideValue, ProfileType

from .base import TABLE_OPTS, Snowflake, SQLBase

__all__ = ["SQLPermissionOverrideTable"]


class SQLPermissionOverrideTable(SQLBase):
    """SQL model for command-specific permission overrides.

    Each row overrides the access level for one command on one profile.

    **Primary keys:** [`bot_id`][], [`profile_id`][], [`profile_type`][], [`command_name`][]
    """

    __tablename__ = "permission_override"

    bot_id: Mapped[Snowflake] = mapped_column(primary_key=True)
    """Discord application ID of the bot this override belongs to."""
    profile_id: Mapped[Snowflake] = mapped_column(primary_key=True)
    """Discord snowflake ID of the target user or role."""
    profile_type: Mapped[ProfileType] = mapped_column(primary_key=True)
    """[ProfileType][]{ data-preview } indicating whether [`profile_id`][] is a user or a role."""
    command_name: Mapped[str] = mapped_column(String(256), primary_key=True)
    """Qualified name of the command being overridden (e.g. `"reply"`)."""
    override_value: Mapped[PermissionOverrideValue]
    """[PermissionOverrideValue][]{ data-preview } for this command."""

    __table_args__ = (
        ForeignKeyConstraint(
            ["bot_id", "profile_id", "profile_type"],
            ["profile.bot_id", "profile.profile_id", "profile.profile_type"],
            name="fk_permission_override_profile",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        TABLE_OPTS,
    )
