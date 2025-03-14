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
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from modmail import __version__
from modmail.backends import DBClientBase, Settings
from modmail.errors import DatabaseConnectionError

from .migration import do_migration
from .models import SQLSettingsModel

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
            self.__settings = result.scalar_one_or_none()
            if self.__settings is None:
                logger.debug("Settings not found in SQL database. Creating new settings.")
                self.__settings = SQLSettingsModel(bot_id=self._config.bot.bot_id)
                session.add(self.__settings)
                await session.commit()
            logger.debug("Loaded settings from SQL database.")

    async def disconnect(self) -> None:
        """
        Close the connection to the SQL database.
        """
        if self.engine:
            await self.engine.dispose()
            logger.debug("Disconnected from SQL database.")

    async def get_last_ran_version(self) -> str | None:
        """
        Get the last ran version of the bot.
        """
        return self._settings.last_ran_version

    async def update_last_ran_version(self) -> None:
        """
        Update the last ran version of the bot to the current version.
        """
        self._settings.last_ran_version = __version__
        assert self._async_session is not None, "Session is not initialized."
        try:
            async with self._async_session() as session:
                session.add(self._settings)
                await session.commit()
            logger.debug("Updated last ran version to %s", __version__)
        except SQLAlchemyError as e:
            logger.critical("Failed to update the last ran version in SQL database.")
            raise DatabaseConnectionError from e
