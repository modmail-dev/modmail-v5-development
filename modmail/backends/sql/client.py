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

from sqlalchemy import and_, delete, event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from modmail.backends import DBClientBase, PermissionGroup, Settings
from modmail.enum import PermissionGroupKey, PermissionGroupType
from modmail.errors import DatabaseConnectionError

from .migration import do_migration
from .models import *

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.pool import ConnectionPoolEntry

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
        self.engine: AsyncEngine | None = None
        self._async_session: async_sessionmaker[AsyncSession] | None = None
        self.__settings_table: SQLSettingsTable | None = None
        self.__settings_model: Settings | None = None

        # Permission groups are loaded from the database on startup.
        self.__permission_groups: dict[PermissionGroupKey, tuple[SQLPermissionGroupTable, PermissionGroup]] = {}

    @property
    def _settings_table(self) -> SQLSettingsTable:
        assert self.__settings_table is not None, "Settings not loaded."
        return self.__settings_table

    @_settings_table.setter
    def _settings_table(self, settings_table: SQLSettingsTable) -> None:
        self.__settings_table = settings_table
        self.__settings_model = Settings.model_validate(settings_table)

    @property
    def settings_model(self) -> Settings:
        assert self.__settings_model is not None, "Settings model not loaded."
        return self.__settings_model

    @property
    def _sql_config(self) -> SQLDatabaseConfig:
        assert self._config.sql_config is not None, "SQL config is not set."
        return self._config.sql_config

    async def connect(self) -> None:
        self.engine = engine = create_async_engine(self._sql_config.uri.get_secret_value())

        # noinspection PyUnusedLocal
        @event.listens_for(self.engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry) -> None:
            """
            Set the SQLite PRAGMA foreign_keys to ON for the connection.
            This is required to enforce foreign key constraints in SQLite.
            """
            if engine.dialect.name.casefold() == "sqlite":
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON;")
                cursor.close()

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
        async with self._async_session() as session:
            query = select(SQLSettingsTable).where(SQLSettingsTable.bot_id == self._config.bot.bot_id)
            result = await session.execute(query)
            settings_table = result.scalar_one_or_none()
            if settings_table is None:
                logger.debug("Settings not found in SQL database. Creating new settings.")
                settings_table = SQLSettingsTable(bot_id=self._config.bot.bot_id)
                session.add(settings_table)
                await session.commit()
            session.expunge(settings_table)  # Detach the settings from the session
            self._settings_table = settings_table
            logger.debug("Loaded settings from SQL database.")

        await self._sync_permission_groups()

    async def disconnect(self) -> None:
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            logger.debug("Disconnected from SQL database.")

    async def sync_settings(self) -> None:
        """
        Sync the settings from the SQL database.
        This is used to ensure that the settings are up-to-date with the database.
        """
        assert self._async_session is not None, "Session is not initialized."
        async with self._async_session() as session:
            query = select(SQLSettingsTable).where(SQLSettingsTable.bot_id == self._config.bot.bot_id)
            result = await session.execute(query)
            settings_table = result.scalar_one()
            session.expunge(settings_table)
            self._settings_table = settings_table

    async def update_settings(self, **kwargs: Any) -> None:
        # Validate the kwargs, by creating a new Settings object with the provided kwargs.
        # Uses a new Settings model to avoid modifying the original settings and validate the new settings.
        new_settings = Settings(
            **self.settings_model.model_dump(exclude={key: True for key in kwargs.keys()}), **kwargs
        )
        settings_dict = new_settings.model_dump(include={key: True for key in kwargs.keys()} | {"bot_id": True})
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

                session.expunge(settings_table)  # Detach the settings from the session
                self._settings_table = settings_table  # Update the settings model

        except Exception as e:
            logger.debug("Failed to update settings in SQL database.", exc_info=True)
            logger.critical("An unknown error occurred while updating settings in SQL database.")
            await self.sync_settings()
            raise DatabaseConnectionError from e

    @staticmethod
    def _make_perm_group_from_table(group: SQLPermissionGroupTable) -> PermissionGroup:
        """
        Convert a SQLPermissionGroupTable object to a PermissionGroup object.
        """
        attributes = {
            field: getattr(group, field)
            for field in SQLPermissionGroupTable.__table__.columns.keys()
            if field != "overrides"
        }
        attributes["overrides"] = {override.command_name: override.override_value for override in group.overrides}
        return PermissionGroup(**attributes)

    async def _sync_permission_groups(self) -> None:
        """
        Sync the permission groups from the database to the local cache.
        """
        assert self._async_session is not None, "Session is not initialized."
        self.__permission_groups.clear()
        async with self._async_session() as session:
            query = select(SQLPermissionGroupTable).where(
                SQLPermissionGroupTable.bot_id == self._config.bot.bot_id
            )
            results = (await session.execute(query)).scalars().fetchall()
            for group in results:
                group_key = PermissionGroupKey(group.group_id, group.group_type)
                self.__permission_groups[group_key] = (group, self._make_perm_group_from_table(group))
                session.expunge(group)
        logger.debug("Synchronized permission groups from SQL database.")

    def get_permission_group(self, group_id: int, group_type: PermissionGroupType) -> PermissionGroup | None:
        group_key = PermissionGroupKey(group_id, group_type)
        if group_key in self.__permission_groups:
            return self.__permission_groups[group_key][1]
        return None

    async def update_permission_group(self, perm_group: PermissionGroup) -> None:
        assert self._async_session is not None, "Session is not initialized."

        group_key = PermissionGroupKey(perm_group.group_id, perm_group.group_type)
        permission_group_dict = perm_group.model_dump(exclude={"group_id", "group_type"})
        all_overrides = perm_group.overrides.copy()

        assert permission_group_dict.pop("bot_id") == self._config.bot.bot_id, "Bot ID mismatch."

        async with self._async_session() as session:
            if group_key in self.__permission_groups:
                # Update the existing permission group
                group = await session.merge(self.__permission_groups[group_key][0])
                for key, value in permission_group_dict.items():
                    if key == "overrides":
                        for override in group.overrides.copy():
                            if (override_value := all_overrides.pop(override.command_name, None)) is not None:
                                if override_value != override.override_value:
                                    # Update the override value of an existing override entry
                                    override.override_value = override_value
                            else:
                                # If the override is no longer in new overrides, delete it
                                group.overrides.remove(override)

                        # Add new overrides
                        for command_name, override_value in all_overrides.items():
                            new_override = SQLPermissionGroupOverrideTable(
                                bot_id=self._config.bot.bot_id,
                                group_id=perm_group.group_id,
                                group_type=perm_group.group_type,
                                command_name=command_name,
                                override_value=override_value,
                            )
                            group.overrides.append(new_override)
                    else:
                        setattr(group, key, value)

                await session.commit()
                session.expunge(group)
                self.__permission_groups[group_key] = (group, self._make_perm_group_from_table(group))
                logger.debug("Updated permission group in SQL database: %s", group_key)
            else:
                # Create a new permission group

                # Convert overrides: {command_name: override_type, ...} to a list of SQLPermissionGroupOverrideTable objects
                overrides = [
                    SQLPermissionGroupOverrideTable(
                        bot_id=self._config.bot.bot_id,
                        group_id=perm_group.group_id,
                        group_type=perm_group.group_type,
                        command_name=command_name,
                        override_value=override_value,
                    )
                    for command_name, override_value in all_overrides.items()
                ]
                permission_group_dict["overrides"] = overrides

                group = SQLPermissionGroupTable(
                    bot_id=self._config.bot.bot_id,
                    group_id=perm_group.group_id,
                    group_type=perm_group.group_type,
                    **permission_group_dict,
                )
                session.add(group)
                await session.commit()
                session.expunge(group)
                self.__permission_groups[group_key] = (group, self._make_perm_group_from_table(group))
                logger.debug("Created new permission group in SQL database: %s", group_key)

    async def delete_permission_group(self, group_id: int, group_type: PermissionGroupType | None) -> None:
        assert self._async_session is not None, "Session is not initialized."

        if group_type is None:
            for key in list(self.__permission_groups.keys()):
                if key.group_id == group_id:
                    del self.__permission_groups[key]
        else:
            group_key = PermissionGroupKey(group_id, group_type)
            self.__permission_groups.pop(group_key, None)  # Remove from local cache

        async with self._async_session() as session:
            query = delete(SQLPermissionGroupTable).where(
                and_(
                    SQLPermissionGroupTable.bot_id == self._config.bot.bot_id,
                    SQLPermissionGroupTable.group_id == group_id,
                )
            )
            await session.execute(query)
            await session.commit()
            logger.debug("Deleted permission group from SQL database: %s", group_id)
