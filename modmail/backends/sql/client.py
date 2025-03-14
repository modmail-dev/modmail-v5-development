"""
modmail.backends.sql.client
===========================
This module provides the SQL database client using SQLAlchemy for connecting to a SQL database,
handling initialization and settings management for the Modmail bot.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from modmail.backends import DBClientBase, Settings
from modmail.errors import DatabaseConnectionError

from .migration import do_migration
from .models import SQLActivityModel, SQLSettingsModel

if TYPE_CHECKING:
    from modmail.config.models import Config, SQLDatabaseConfig


logger = logging.getLogger(__name__)


class SQLClient(DBClientBase):
    """
    SQLClient is a wrapper around a SQL database using SQLAlchemy.
    It connects to the database, loads or creates the bot settings,
    and provides methods to get and update the last ran version.
    """

    def __init__(self, config: Config):
        super().__init__(config)
        self.engine = None
        self._async_session: async_sessionmaker[AsyncSession] | None = None
        self.__settings: SQLSettingsModel | None = None
        self.__settings_model: Settings | None = None

    @property
    def _settings(self) -> SQLSettingsModel:
        assert self.__settings is not None, "Settings not loaded."
        return self.__settings

    @_settings.setter
    def _settings(self, settings: SQLSettingsModel) -> None:
        self.__settings = settings
        self.__settings_model = Settings.model_validate(settings)

    @property
    def settings_model(self) -> Settings:
        assert self.__settings_model is not None, "Settings model not loaded."
        return self.__settings_model

    @property
    def _sql_config(self) -> SQLDatabaseConfig:
        assert self._config.sql_config is not None, "SQL config is not set."
        return self._config.sql_config

    async def connect(self) -> None:
        """
        Create the async engine and session, then load the settings.
        """
        self.engine = create_async_engine(self._sql_config.uri.get_secret_value())
        self._async_session = async_sessionmaker(self.engine, expire_on_commit=False)

        try:
            # Test the connection to the database
            async with self.engine.begin():
                logger.debug("Connected to SQL database.")
        except SQLAlchemyError as e:
            logger.debug("Failed to connect to SQL database.", exc_info=True)
            logger.critical("An error occurred while connecting to SQL database.")
            raise DatabaseConnectionError from e
        except Exception as e:
            logger.debug("An unknown error occurred during SQL connection.", exc_info=True)
            logger.critical("An unknown error occurred during SQL connection.")
            raise DatabaseConnectionError from e

        loop = asyncio.get_running_loop()

        logger.debug("Running database migrations.")

        with ProcessPoolExecutor() as pool:
            # Run the migration in a separate process.
            await loop.run_in_executor(pool, do_migration, self._sql_config.uri.get_secret_value())

        # Load settings from the SQL database
        async with self._async_session() as session:
            query = select(SQLSettingsModel).where(SQLSettingsModel.bot_id == self._config.bot.bot_id)
            result = await session.execute(query)
            sql_settings = result.scalar_one_or_none()
            if sql_settings is None:
                logger.debug("Settings not found in SQL database. Creating new settings.")
                sql_settings = SQLSettingsModel(bot_id=self._config.bot.bot_id)
                session.add(sql_settings)
                await session.commit()
            session.expunge(sql_settings)  # Detach the settings from the session
            self._settings = sql_settings
            logger.debug("Loaded settings from SQL database.")

    async def disconnect(self) -> None:
        """
        Close the connection to the SQL database.
        """
        if self.engine:
            await self.engine.dispose()
            logger.debug("Disconnected from SQL database.")

    async def sync_settings(self) -> None:
        """
        Sync the settings from the SQL database.
        This is used to ensure that the settings are up-to-date with the database.
        """
        assert self._async_session is not None, "Session is not initialized."
        async with self._async_session() as session:
            query = select(SQLSettingsModel).where(SQLSettingsModel.bot_id == self._config.bot.bot_id)
            result = await session.execute(query)
            sql_settings = result.scalar_one()
            session.expunge(sql_settings)
            self._settings = sql_settings

    async def update_settings(self, **kwargs: Any) -> None:
        # Validate the kwargs, by creating a new Settings object with the provided kwargs.
        # Uses a new Settings model to avoid modifying the original settings and validate the new settings.
        new_settings = Settings(
            **self.settings_model.model_dump(exclude={key: True for key in kwargs.keys()}), **kwargs
        )
        settings_dict = new_settings.model_dump(include={key: True for key in kwargs.keys()} | {"bot_id": True})
        logger.debug("Updating settings in SQL database: %s", settings_dict)

        assert self._async_session is not None, "Session is not initialized."
        assert settings_dict["bot_id"] == self._config.bot.bot_id, "Bot ID mismatch."

        try:
            async with self._async_session() as session:
                sql_settings = await session.merge(self._settings)

                if "activity" in settings_dict:
                    activity = settings_dict.pop("activity")
                    if activity is not None:
                        # Convert the activity dict to SQLActivityModel
                        sql_settings.activity = SQLActivityModel(**activity, bot_id=self._config.bot.bot_id)
                        await session.merge(sql_settings.activity)
                    else:
                        query = delete(SQLActivityModel).where(SQLActivityModel.bot_id == self._config.bot.bot_id)
                        await session.execute(query)
                        sql_settings.activity = None

                # Update the settings in the database
                for key, value in settings_dict.items():
                    setattr(sql_settings, key, value)

                await session.commit()

                session.expunge(sql_settings)  # Detach the settings from the session
                self._settings = sql_settings  # Update the settings model

        except Exception as e:
            logger.debug("Failed to update settings in SQL database.", exc_info=True)
            logger.critical("An unknown error occurred while updating settings in SQL database.")
            await self.sync_settings()
            raise DatabaseConnectionError from e
