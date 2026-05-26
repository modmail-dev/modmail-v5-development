"""Reads and writes bot settings, creating a default document on first access."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pymongo.errors

from modmail.errors import DatabaseOperationError

from ._base import MongoDBBackendBase
from .models import MongoDBSettingsDocument

if TYPE_CHECKING:
    from modmail.backends.common import SettingsModel

logger = logging.getLogger(__name__)


class MongoDBSettingsMixin(MongoDBBackendBase):
    """MongoDB mixin implementing settings operations."""

    async def fetch_settings(self) -> SettingsModel:
        """Load the settings document for this `bot_id`, creating it with defaults if absent.

        Returns:
            SettingsModel: The current settings.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            settings_document = await MongoDBSettingsDocument.find_one(
                MongoDBSettingsDocument.bot_id == self._config.bot.bot_id
            )
            if settings_document is None:
                logger.debug("Settings not found in MongoDB — creating default settings.")
                settings_document = MongoDBSettingsDocument(bot_id=self._config.bot.bot_id)
                await settings_document.insert()
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to fetch settings") from exc
        return settings_document.to_model()

    async def persist_settings(self, model: SettingsModel) -> None:
        """Upsert the settings document for this `bot_id`.

        Args:
            model: The new [SettingsModel][]{ data-preview } to persist.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
            ValueError: If the model's `bot_id` does not match the backend's `bot_id`.
        """
        if model.bot_id != self._config.bot.bot_id:
            raise ValueError("Invalid bot ID")
        await MongoDBSettingsDocument.put_model(model)
