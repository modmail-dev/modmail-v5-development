"""SQLAlchemy models for permission profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.backends.common.models import ProfileModel
from modmail.enum import AccessLevel, ProfileType

from .base import TABLE_OPTS, Snowflake, SQLBase
from .permission_override_model import SQLPermissionOverrideTable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["SQLProfileTable"]


class SQLProfileTable(SQLBase):
    """SQL model for user or role permission profiles.

    Command-specific overrides are in the [`permission_overrides`][] collection.

    **Primary keys:** [`bot_id`][], [`profile_id`][], [`profile_type`][]
    """

    __tablename__ = "profile"

    bot_id: Mapped[Snowflake] = mapped_column(
        ForeignKey("settings.bot_id", ondelete="CASCADE", onupdate="CASCADE")
    )
    """Discord application ID of the bot this profile belongs to."""
    profile_id: Mapped[Snowflake]
    """Discord snowflake ID of the target user or role."""
    profile_type: Mapped[ProfileType]
    """[ProfileType][]{ data-preview } indicating whether [`profile_id`][] is a user or a role."""
    access_level: Mapped[AccessLevel | None]
    """[AccessLevel][]{ data-preview } granted by this profile (`None` if unset)."""
    permission_overrides: Mapped[list[SQLPermissionOverrideTable]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )
    """[SQLPermissionOverrideTable][]{ data-preview } overrides for individual commands."""
    tag: Mapped[str | None] = mapped_column(String(128))
    """Short display label for this profile (`None` if unset)."""
    color: Mapped[int | None] = mapped_column(Integer())
    """Discord color integer, e.g. `0xFFFFFF` for white (`None` if unset)."""

    __table_args__ = (PrimaryKeyConstraint("bot_id", "profile_id", "profile_type"), TABLE_OPTS)

    def to_model(self) -> ProfileModel:
        """Convert this row to a [ProfileModel][]{ data-preview }.

        Returns:
            ProfileModel: The converted common profile model.
        """
        return ProfileModel(
            bot_id=self.bot_id,
            profile_id=self.profile_id,
            profile_type=self.profile_type,
            access_level=self.access_level,
            tag=self.tag,
            color=self.color,
            permission_overrides={
                override.command_name: override.override_value for override in self.permission_overrides
            },
        )

    @classmethod
    async def put_model(cls, model: ProfileModel, session: AsyncSession) -> None:
        """Upsert a profile row and its permission overrides within an open session.

        If a matching row already exists (same [`bot_id`][], [`profile_id`][], and
        [`profile_type`][]), scalar fields are updated in place and the
        [`permission_overrides`][] collection is diffed. Only changed, added, or
        removed overrides are written. If no row exists, the profile and all its
        overrides are inserted.

        Note:
            Must be called inside an active `session.begin()` block. The caller is
            responsible for committing or rolling back the transaction.

        Args:
            model: The profile to create or update.
            session: An open [AsyncSession][] with an active transaction.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: If an unexpected database error occurs.
        """
        row = await session.get(cls, (model.bot_id, model.profile_id, model.profile_type))
        update_dict = model.model_dump(exclude={"bot_id", "profile_id", "profile_type", "permission_overrides"})

        if row is None:
            row = cls(
                bot_id=model.bot_id, profile_id=model.profile_id, profile_type=model.profile_type, **update_dict
            )
            for cmd_name, value in model.permission_overrides.items():
                row.permission_overrides.append(
                    SQLPermissionOverrideTable(
                        bot_id=model.bot_id,
                        profile_id=model.profile_id,
                        profile_type=model.profile_type,
                        command_name=cmd_name,
                        override_value=value,
                    )
                )
            session.add(row)
            return

        existing = {o.command_name: o for o in row.permission_overrides}
        incoming = dict(model.permission_overrides)
        for cmd_name, override_obj in existing.items():
            if cmd_name not in incoming:
                row.permission_overrides.remove(override_obj)
            else:
                override_obj.override_value = incoming[cmd_name]
        for cmd_name, value in incoming.items():
            if cmd_name not in existing:
                row.permission_overrides.append(
                    SQLPermissionOverrideTable(
                        bot_id=model.bot_id,
                        profile_id=model.profile_id,
                        profile_type=model.profile_type,
                        command_name=cmd_name,
                        override_value=value,
                    )
                )

        for k, v in update_dict.items():
            setattr(row, k, v)
