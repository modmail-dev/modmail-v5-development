"""Reads, writes, and removes permission profiles and their per-command overrides."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pymongo.errors

from modmail.errors import DatabaseOperationError

from ._base import MongoDBBackendBase
from .models import MongoDBProfileDocument

if TYPE_CHECKING:
    from ..common.models import ProfileModel


class MongoDBProfilesMixin(MongoDBBackendBase):
    """MongoDB mixin implementing profile read/write operations."""

    async def fetch_all_profiles(self) -> list[ProfileModel]:
        """Return all profile documents for this `bot_id`.

        Returns:
            list[ProfileModel]: One [ProfileModel][]{ data-preview } per stored profile.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            profiles = [
                doc.to_model()
                async for doc in MongoDBProfileDocument.find(
                    MongoDBProfileDocument.bot_id == self._config.bot.bot_id
                )
            ]
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to fetch profiles") from exc

        return profiles

    async def persist_profile(self, profile: ProfileModel) -> None:
        """Upsert a profile document in MongoDB.

        Args:
            profile: The [ProfileModel][]{ data-preview } to create or update.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
            ValueError: If the profile's `bot_id` does not match the backend's `bot_id`.
        """
        if profile.bot_id != self._config.bot.bot_id:
            raise ValueError("Invalid bot ID")
        await MongoDBProfileDocument.put_model(profile)

    async def remove_profile(self, profile_id: int) -> None:
        """Delete all profile documents for the given `profile_id` under this `bot_id`.

        Args:
            profile_id: The identifier of the profile to delete. All profile
                types sharing this ID are removed.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            await MongoDBProfileDocument.find(
                MongoDBProfileDocument.bot_id == self._config.bot.bot_id,
                MongoDBProfileDocument.profile_id == profile_id,
            ).delete()
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to remove profile") from exc
