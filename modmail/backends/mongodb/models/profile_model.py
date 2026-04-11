"""Beanie document model for permission profiles in MongoDB."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pymongo.errors
from beanie import Document
from pymongo import ASCENDING, IndexModel

from modmail.backends.common import ProfileModel
from modmail.enum import AccessLevel, PermissionOverrideValue, ProfileType
from modmail.errors import DatabaseOperationError

from .base import BSON_ENCODERS

if TYPE_CHECKING:
    from beanie.odm.queries.update import UpdateOne

__all__ = ["MongoDBProfileDocument"]


class MongoDBProfileDocument(Document):
    """Beanie document for a user or role permission profile.

    Uniquely indexed on ([`bot_id`][], [`profile_id`][], [`profile_type`][]).
    [`permission_overrides`][] maps command names to allow/deny values,
    bypassing the command's access level.
    """

    bot_id: int
    """Discord application ID of the bot this profile belongs to."""
    profile_id: int
    """Discord snowflake ID of the target user or role."""
    profile_type: ProfileType
    """[ProfileType][]{ data-preview } indicating whether [`profile_id`][] is a user or a role."""
    access_level: AccessLevel | None = None
    """[AccessLevel][]{ data-preview } granted by this profile (`None` if unset)."""

    permission_overrides: dict[str, PermissionOverrideValue] = {}
    """Per-command [PermissionOverrideValue][]{ data-preview } overrides."""

    tag: str | None = None
    """Short display label for this profile (`None` if unset)."""
    colour: int | None = None
    """Discord color integer, e.g. `0xFFFFFF` for white (`None` if unset)."""

    class Settings:
        """Settings for MongoDB permission profile collection."""

        name = "Profile"
        keep_nulls = False
        validate_on_save = True
        bson_encoders = BSON_ENCODERS
        indexes = [
            IndexModel(
                [("bot_id", ASCENDING), ("profile_id", ASCENDING), ("profile_type", ASCENDING)],
                unique=True,
                name="profile_unique",
            )
        ]

    def to_model(self) -> ProfileModel:
        """Convert this document to a common [ProfileModel][]{ data-preview }.

        Returns:
            ProfileModel: The converted common profile model.
        """
        return ProfileModel.model_validate(self.model_dump())

    @classmethod
    async def put_model(cls, model: ProfileModel) -> None:
        """Upsert a profile document in MongoDB from a common [ProfileModel][]{ data-preview }.

        Updates the existing document for this ([`bot_id`][], [`profile_id`][], [`profile_type`][])
        in-place, or inserts a new document if none exists.

        Args:
            model: The profile to create or update.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        doc = cls.model_validate(model.model_dump())
        update_dict = doc.model_dump(exclude={"id", "bot_id", "profile_id", "profile_type"})
        try:
            await cast(
                "UpdateOne",
                cls.find_one(
                    cls.bot_id == model.bot_id,
                    cls.profile_id == model.profile_id,
                    cls.profile_type == model.profile_type,
                ).upsert({"$set": update_dict}, on_insert=doc),
            )
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to persist profile") from exc
