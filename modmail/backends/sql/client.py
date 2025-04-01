"""SQL database client module for Modmail.

This module provides the SQL database client using SQLAlchemy for connecting to a SQL database,
handling initialization and settings management for the Modmail bot.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, delete, event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from modmail.enum import ProfileKey, ProfileType
from modmail.errors import DatabaseConnectionError

from ..common import DBClientBase, Profile, Settings
from .migration import do_migration
from .models import SQLActivityTable, SQLPermissionOverrideTable, SQLProfileTable, SQLSettingsTable

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.pool import ConnectionPoolEntry

    from modmail.config.models import Config, SQLDatabaseConfig

__all__ = ["SQLClient"]

logger = logging.getLogger(__name__)


class SQLClient(DBClientBase):
    """SQL database client using SQLAlchemy.

    A wrapper around a SQL database connection that handles initialization,
    settings management, and profile operations for the Modmail bot.
    """

    def __init__(self, config: Config) -> None:
        """Initialize the SQL client.

        Args:
            config: Bot configuration containing database connection details.
        """
        super().__init__(config)
        self.engine: AsyncEngine | None = None
        self._async_session: async_sessionmaker[AsyncSession] | None = None
        self.__settings_table: SQLSettingsTable | None = None
        self.__settings_model: Settings | None = None

        # Profiles are loaded and cached from the database on startup.
        self.__profiles_cache: dict[ProfileKey, tuple[SQLProfileTable, Profile]] = {}

    @property
    def _settings_table(self) -> SQLSettingsTable:
        """Get the settings table object.

        Returns:
            The SQLAlchemy settings table object.
        """
        assert self.__settings_table is not None, "Settings not loaded."
        return self.__settings_table

    @_settings_table.setter
    def _settings_table(self, settings_table: SQLSettingsTable) -> None:
        """Set the settings table and update the settings model.

        Args:
            settings_table: The SQLAlchemy settings table object.
        """
        self.__settings_table = settings_table
        self.__settings_model = Settings.model_validate(settings_table)

    @property
    def settings_model(self) -> Settings:
        """Get the settings model.

        Returns:
            The settings model object.
        """
        assert self.__settings_model is not None, "Settings model not loaded."
        return self.__settings_model

    @property
    def profiles(self) -> list[Profile]:
        """Get the list of profiles.

        Returns:
            A list of profile objects.
        """
        return [profile[1] for profile in self.__profiles_cache.values()]

    @property
    def _sql_config(self) -> SQLDatabaseConfig:
        """Get the SQL database configuration.

        Returns:
            The SQL database configuration.
        """
        assert self._config.sql_config is not None, "SQL config is not set."
        return self._config.sql_config

    async def connect(self) -> None:
        """Connect to the SQL database and initialize settings.

        Establishes a connection to the SQL database, runs migrations,
        and loads or creates settings for the bot.

        Raises:
            DatabaseConnectionError: If unable to connect to the database.
        """
        self.engine = engine = create_async_engine(self._sql_config.uri.get_secret_value())

        # noinspection PyUnusedLocal
        @event.listens_for(self.engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry) -> None:
            """Set the SQLite PRAGMA foreign_keys to ON for the connection.

            This is required to enforce foreign key constraints in SQLite.

            Args:
                dbapi_connection: The database connection.
                connection_record: The connection pool entry.
            """
            if engine.dialect.name.casefold() == "sqlite":
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON;")
                cursor.close()  # pragma: no cover ; no idea why coverage thinks this is unreachable

        # noinspection PyAttributeOutsideInit
        self.__set_sqlite_pragma = set_sqlite_pragma  # Keep a reference to the listener function

        self._async_session = async_sessionmaker(self.engine, expire_on_commit=False)

        try:
            # Connect and test the connection to the database
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
        await self.sync_settings()
        await self.sync_profiles()

    async def disconnect(self) -> None:
        """Disconnect from the SQL database.

        Closes all connections to the database and disposes of the engine.
        """
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            logger.debug("Disconnected from SQL database.")

    async def sync_settings(self) -> None:
        """Sync the settings from the SQL database.

        Refreshes the local settings from the database to ensure they are up-to-date.
        If the settings do not exist in the database, a new settings entry is created.
        """
        assert self._async_session is not None, "Session is not initialized."
        async with self._async_session() as session:
            query = select(SQLSettingsTable).where(SQLSettingsTable.bot_id == self._config.bot.bot_id)
            result = await session.execute(query)
            settings_table = result.scalar_one_or_none()
            if settings_table is None:
                logger.debug("Settings not found in SQL database. Creating new settings.")
                settings_table = SQLSettingsTable(bot_id=self._config.bot.bot_id)
                session.add(settings_table)
                await session.commit()
                await session.refresh(settings_table)  # Make sure all relationships are loaded
            session.expunge(settings_table)
        self._settings_table = settings_table
        logger.debug("Synchronized settings from SQL database.")

    async def update_settings(self, **kwargs: Any) -> None:
        """Update bot settings in the database.

        Updates the specified settings in the database and refreshes the local settings.

        Args:
            **kwargs: Settings key-value pairs to update.

        Raises:
            DatabaseConnectionError: If an error occurs while updating settings.
        """
        # Validate the kwargs, by creating a new Settings object with the provided kwargs.
        # Uses a new Settings model to avoid modifying the original settings and validate the new settings.
        new_settings = Settings(**self.settings_model.model_dump(exclude=dict.fromkeys(kwargs, True)), **kwargs)
        settings_dict = new_settings.model_dump(include=dict.fromkeys(kwargs, True) | {"bot_id": True})
        logger.debug("Updating settings in SQL database: %s", settings_dict)

        assert self._async_session is not None, "Session is not initialized."
        assert settings_dict.pop("bot_id") == self._config.bot.bot_id, "Bot ID mismatch."

        try:
            async with self._async_session() as session:
                settings_table = await session.merge(self._settings_table)

                if "activity" in settings_dict:
                    activity = settings_dict.pop("activity")
                    if activity is not None:
                        # Convert the activity dict to SQLActivityModel
                        settings_table.activity = SQLActivityTable(**activity, bot_id=self._config.bot.bot_id)
                        await session.merge(settings_table.activity)
                    else:
                        query = delete(SQLActivityTable).where(SQLActivityTable.bot_id == self._config.bot.bot_id)
                        await session.execute(query)
                        settings_table.activity = None

                # Update the settings in the database
                for key, value in settings_dict.items():
                    setattr(settings_table, key, value)

                await session.commit()
                await session.refresh(settings_table)  # Refresh the settings table to get the latest data

                session.expunge(settings_table)  # Detach the settings from the session
                self._settings_table = settings_table  # Update the settings model

        except Exception as e:
            logger.debug("Failed to update settings in SQL database.", exc_info=True)
            logger.critical("An unknown error occurred while updating settings in SQL database.")
            await self.sync_settings()
            raise DatabaseConnectionError from e

    @staticmethod
    def _make_profile_from_table(profile_row: SQLProfileTable) -> Profile:
        """Convert a SQLProfileTable object to a Profile object.

        Args:
            profile_row: Database profile row to convert.

        Returns:
            A Profile model instance populated with data from the database row.
        """
        attributes = {
            field: getattr(profile_row, field)
            for field in SQLProfileTable.__table__.columns.keys()  # noqa: SIM118
            if field != "permission_overrides"
        }
        attributes["permission_overrides"] = {
            override.command_name: override.override_value for override in profile_row.permission_overrides
        }
        return Profile(**attributes)

    async def sync_profiles(self) -> None:
        """Sync profiles from the database to the local cache.

        Fetches all profiles from the database and stores them in the local cache.
        """
        assert self._async_session is not None, "Session is not initialized."
        profiles_cache: dict[ProfileKey, tuple[SQLProfileTable, Profile]] = {}
        async with self._async_session() as session:
            query = select(SQLProfileTable).where(SQLProfileTable.bot_id == self._config.bot.bot_id)
            results = (await session.execute(query)).scalars().fetchall()
            for profile_row in results:
                profile_key = ProfileKey(profile_row.profile_id, profile_row.profile_type)
                profiles_cache[profile_key] = (profile_row, self._make_profile_from_table(profile_row))
                session.expunge(profile_row)
        self.__profiles_cache = profiles_cache
        logger.debug("Synchronized profiles from SQL database.")

    def get_profile(self, profile_id: int, profile_type: ProfileType) -> Profile | None:
        """Get a profile from the cache.

        Args:
            profile_id: ID of the profile to retrieve.
            profile_type: Type of the profile to retrieve.

        Returns:
            The profile if found, None otherwise.
        """
        profile_key = ProfileKey(profile_id, profile_type)
        if profile_key in self.__profiles_cache:
            return self.__profiles_cache[profile_key][1]
        return None

    async def update_profile(self, profile: Profile) -> None:
        """Update or create a profile in the database.

        If the profile exists, updates its properties. If not, creates a new profile.
        Also updates the local cache accordingly.

        Args:
            profile: The profile to update or create.
        """
        assert self._async_session is not None, "Session is not initialized."

        profile_key = ProfileKey(profile.profile_id, profile.profile_type)
        new_profile_dict = profile.model_dump(exclude={"profile_id", "profile_type"})
        new_permission_overrides = profile.permission_overrides.copy()

        assert new_profile_dict.pop("bot_id") == self._config.bot.bot_id, "Bot ID mismatch."

        async with self._async_session() as session:
            if profile_key in self.__profiles_cache:
                # Update the existing profile
                profile_row = await session.merge(self.__profiles_cache[profile_key][0])
                for key, value in new_profile_dict.items():
                    if key == "permission_overrides":
                        to_remove: list[SQLPermissionOverrideTable] = []

                        for old_override in profile_row.permission_overrides:
                            if (
                                new_override_value := new_permission_overrides.pop(old_override.command_name, None)
                            ) is not None:
                                if new_override_value != old_override.override_value:
                                    # Update the override value of an existing override entry
                                    old_override.override_value = new_override_value
                            else:
                                # If the override is no longer in new overrides, mark it for removal
                                to_remove.append(old_override)

                        for old_override in to_remove:
                            profile_row.permission_overrides.remove(old_override)

                        # Add new overrides
                        for command_name, new_override_value in new_permission_overrides.items():
                            new_override = SQLPermissionOverrideTable(
                                bot_id=self._config.bot.bot_id,
                                profile_id=profile.profile_id,
                                profile_type=profile.profile_type,
                                command_name=command_name,
                                override_value=new_override_value,
                            )
                            profile_row.permission_overrides.append(new_override)
                    else:
                        setattr(profile_row, key, value)

                await session.commit()
                await session.refresh(profile_row)  # Refresh the profile row to get the latest data
                session.expunge(profile_row)
                self.__profiles_cache[profile_key] = (profile_row, self._make_profile_from_table(profile_row))
                logger.debug("Updated profile %s in SQL database.", profile_key)
            else:
                # Create a new profile

                # Convert overrides: {command_name: override_type, ...} to a list of SQLPermissionOverrideTable
                overrides = [
                    SQLPermissionOverrideTable(
                        bot_id=self._config.bot.bot_id,
                        profile_id=profile.profile_id,
                        profile_type=profile.profile_type,
                        command_name=command_name,
                        override_value=override_value,
                    )
                    for command_name, override_value in new_permission_overrides.items()
                ]
                new_profile_dict["permission_overrides"] = overrides

                profile_row = SQLProfileTable(
                    bot_id=self._config.bot.bot_id,
                    profile_id=profile.profile_id,
                    profile_type=profile.profile_type,
                    **new_profile_dict,
                )
                session.add(profile_row)
                await session.commit()
                await session.refresh(profile_row)
                session.expunge(profile_row)
                self.__profiles_cache[profile_key] = (profile_row, self._make_profile_from_table(profile_row))
                logger.debug("Created new profile in SQL database: %s", profile_key)

    async def delete_profile(self, profile_id: int) -> None:
        """Delete a profile from the database.

        Removes the profile from both the database and the local cache.

        Args:
            profile_id: ID of the profile to delete.
        """
        assert self._async_session is not None, "Session is not initialized."

        async with self._async_session() as session:
            query = delete(SQLProfileTable).where(
                and_(
                    SQLProfileTable.bot_id == self._config.bot.bot_id,
                    SQLProfileTable.profile_id == profile_id,
                )
            )
            await session.execute(query)
            await session.commit()

        for profile_key in list(self.__profiles_cache.keys()):
            if profile_key.profile_id == profile_id:
                del self.__profiles_cache[profile_key]

        logger.debug("Deleted profile from SQL database: %s", profile_id)
