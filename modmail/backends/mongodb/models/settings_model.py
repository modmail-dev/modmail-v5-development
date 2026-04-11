"""Beanie document model for bot settings in MongoDB."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pymongo.errors
from beanie import Document
from pydantic import BaseModel
from pymongo import ASCENDING, IndexModel

from modmail.backends.common import SettingsModel
from modmail.enum import ActivityType, StatusType
from modmail.errors import DatabaseOperationError

from .base import BSON_ENCODERS

if TYPE_CHECKING:
    from beanie.odm.queries.update import UpdateOne

__all__ = [
    "MongoDBActivityModel",
    "MongoDBSettingsDocument",
]


class MongoDBActivityModel(BaseModel):
    """Bot activity configuration embedded in the settings document.

    [`url`][] is only meaningful for the [`ActivityType.streaming`][] activity type and is not
    validated for other types.
    """

    type: ActivityType
    """[ActivityType][]{ data-preview } controlling how the activity appears in Discord."""
    name: str
    """Display name of the activity shown in the bot's status."""
    url: str | None = None
    """Stream URL (`None` if [`type`][] is not [`ActivityType.streaming`][])."""


class MongoDBSettingsDocument(Document):
    """Beanie document for bot settings.

    One document per bot, unique-indexed on [`bot_id`][]. All fields except
    [`bot_id`][] are optional, where `None` means the value has never been set.
    """

    bot_id: int
    """Discord application ID of the bot these settings belong to."""
    last_ran_version: str | None = None
    """Bot version string from the last startup, e.g. `"v1.2.3"` (`None` on first run)."""
    last_ran_locale: str | None = None
    """BCP-47 locale code active on the previous run, e.g. `"en"` (`None` on first run)."""
    last_slash_synced_version: str | None = None
    """Bot version when slash commands were last synced to Discord (`None` if never synced)."""
    last_slash_minimum_permission_int: int | None = None
    """Default member permission integer from the last slash-command sync (`None` if never synced)."""
    main_category_or_forum_id: int | None = None
    """Discord category or forum channel ID where new ticket channels are created (`None` if unset)."""
    fallback_category_id: int | None = None
    """Discord category ID used when the main category is full or unavailable (`None` if unset)."""
    log_channel_id: int | None = None
    """Discord channel ID where closed-ticket summaries are posted (`None` if unset)."""
    storage_channel_id: int | None = None
    """Discord channel ID used for internal file storage (`None` if unset)."""
    status: StatusType | None = None
    """Bot presence status shown in Discord as a [StatusType][]{ data-preview } (`None` if unset)."""
    activity: MongoDBActivityModel | None = None
    """Bot activity shown in Discord as a [MongoDBActivityModel][]{ data-preview } (`None` if unset)."""

    class Settings:
        """Settings for MongoDB settings collection."""

        name = "Settings"
        keep_nulls = False
        validate_on_save = True
        bson_encoders = BSON_ENCODERS

        indexes = [
            IndexModel(
                [("bot_id", ASCENDING)],
                unique=True,
                name="settings_unique",
            )
        ]

    def to_model(self) -> SettingsModel:
        """Convert this document to a common [SettingsModel][]{ data-preview }.

        Returns:
            SettingsModel: The converted common settings model.
        """
        return SettingsModel.model_validate(self.model_dump())

    @classmethod
    async def put_model(cls, model: SettingsModel) -> None:
        """Upsert a settings document in MongoDB from a common [SettingsModel][]{ data-preview }.

        Updates the existing document for this [`bot_id`][] in-place, or inserts a
        new document if none exists.

        Args:
            model: The settings values to persist.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        doc = cls.model_validate(model.model_dump())
        settings_dict = doc.model_dump(exclude={"id", "bot_id"})
        try:
            await cast(
                "UpdateOne",
                cls.find_one(cls.bot_id == model.bot_id).upsert({"$set": settings_dict}, on_insert=doc),
            )
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to persist settings") from exc
