"""Reads, writes, and removes permission profiles and their per-command overrides."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy.exc
from sqlalchemy import and_, delete, select

from modmail.errors import DatabaseOperationError

from ._base import SQLBackendBase
from .models import SQLProfileTable

if TYPE_CHECKING:
    from ..common.models import ProfileModel


class SQLProfilesMixin(SQLBackendBase):
    """SQL mixin implementing profile read/write operations."""

    async def fetch_all_profiles(self) -> list[ProfileModel]:
        """Return all profile rows for this `bot_id`.

        Returns:
            list[ProfileModel]: One [ProfileModel][]{ data-preview } per stored profile.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            async with self.session() as session:
                rows = (
                    (
                        await session.execute(
                            select(SQLProfileTable).where(SQLProfileTable.bot_id == self._config.bot.bot_id)
                        )
                    )
                    .scalars()
                    .fetchall()
                )
                profiles = [row.to_model() for row in rows]
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to fetch profiles") from exc

        return profiles

    async def persist_profile(self, profile: ProfileModel) -> None:
        """Upsert a profile row and its permission overrides.

        Args:
            profile: The [ProfileModel][]{ data-preview } to create or update.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
            ValueError: If the profile's `bot_id` does not match the backend's `bot_id`.
        """
        if profile.bot_id != self._config.bot.bot_id:
            raise ValueError("Invalid bot ID")
        try:
            async with self.session() as session, session.begin():
                await SQLProfileTable.put_model(profile, session)
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to persist profile") from exc

    async def remove_profile(self, profile_id: int) -> None:
        """Delete all profile rows for the given `profile_id` under this `bot_id`.

        Args:
            profile_id: The identifier of the profile to delete. All profile
                types sharing this ID are removed.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            async with self.session() as session, session.begin():
                await session.execute(
                    delete(SQLProfileTable).where(
                        and_(
                            SQLProfileTable.bot_id == self._config.bot.bot_id,
                            SQLProfileTable.profile_id == profile_id,
                        )
                    )
                )
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to remove profile") from exc
