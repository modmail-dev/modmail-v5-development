"""Reads and writes bot settings, creating a default row on first access."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import sqlalchemy.exc
from sqlalchemy import delete

from modmail.errors import DatabaseOperationError

from ._base import SQLBackendBase
from .models import SQLActivityTable, SQLSettingsTable

if TYPE_CHECKING:
    from ..common.models import SettingsModel

logger = logging.getLogger(__name__)


class SQLSettingsMixin(SQLBackendBase):
    """SQL mixin implementing settings operations."""

    async def fetch_settings(self) -> SettingsModel:
        """Load the settings row for this `bot_id`, creating it with defaults if absent.

        Returns:
            SettingsModel: The current settings.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            async with self.session() as session, session.begin():
                settings_table = await session.get(SQLSettingsTable, self._config.bot.bot_id)
                if settings_table is None:
                    logger.debug("Settings not found — creating default settings.")
                    settings_table = SQLSettingsTable(bot_id=self._config.bot.bot_id)
                    session.add(settings_table)
                return settings_table.to_model()
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to fetch settings") from exc

    async def persist_settings(self, model: SettingsModel) -> None:
        """Upsert the settings row for this `bot_id`.

        Args:
            model: The new [SettingsModel][]{ data-preview } to persist.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
            ValueError: If the model's `bot_id` does not match the backend's `bot_id`.
        """
        if model.bot_id != self._config.bot.bot_id:
            raise ValueError("Invalid bot ID")
        try:
            async with self.session() as session, session.begin():
                if model.activity is not None:
                    await session.merge(SQLActivityTable.from_model(model.activity, bot_id=model.bot_id))
                else:
                    await session.execute(
                        delete(SQLActivityTable).where(SQLActivityTable.bot_id == self._config.bot.bot_id)
                    )
                await session.merge(SQLSettingsTable.from_model(model))
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to persist settings") from exc
