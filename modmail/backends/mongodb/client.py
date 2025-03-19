"""
modmail.backends.mongodb.client
===============================
This module provides the MongoDB client implementation for the Modmail bot.
It includes functionality to connect to the MongoDB database and handle connection errors.
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING, Any

import pymongo.errors
from beanie import init_beanie  # type: ignore[reportUnknownVariableType]  # beanie is not fully typed
from motor.motor_asyncio import AsyncIOMotorClient

from modmail.backends import DBClientBase, PermissionGroup, Settings
from modmail.enum import PermissionGroupKey, PermissionGroupType
from modmail.errors import DatabaseConnectionError

from .migration import do_migration
from .models import *

if TYPE_CHECKING:
    from modmail.config.models import Config, MongoDBDatabaseConfig

__all__ = [
    "MongoDBClient",
]

logger = logging.getLogger(__name__)


class MongoDBClient(DBClientBase):
    """
    MongoDBClient is a wrapper around the MongoDB client that provides
    a simple interface for connecting to the database and performing
    basic operations.
    """

    def __init__(self, config: Config):
        super().__init__(config)
        self.db_name = self._mongodb_config.database
        self._client: AsyncIOMotorClient[dict[str, Any]] | None = None
        self.__settings_document: MongoDBSettingsDocument | None = (
            None  # the loaded settings model from the database
        )
        self.__settings_model: Settings | None = None  # a read-only view of the settings model

        # Permission groups are loaded from the database on startup.
        self.__permission_groups: dict[
            PermissionGroupKey, tuple[MongoDBPermissionGroupDocument, PermissionGroup]
        ] = {}

    @property
    def _settings_document(self) -> MongoDBSettingsDocument:
        assert self.__settings_document is not None, "Settings not loaded."
        return self.__settings_document

    @_settings_document.setter
    def _settings_document(self, settings_document: MongoDBSettingsDocument) -> None:
        self.__settings_document = settings_document
        self.__settings_model = Settings.model_validate(settings_document)

    @property
    def settings_model(self) -> Settings:
        assert self.__settings_model is not None, "Settings model not loaded."
        return self.__settings_model

    @property
    def _mongodb_config(self) -> MongoDBDatabaseConfig:
        assert self._config.mongodb_config is not None, "MongoDB config is not set."
        return self._config.mongodb_config

    async def connect(self) -> None:
        self._client = AsyncIOMotorClient(
            self._mongodb_config.uri.get_secret_value(),
            connectTimeoutMS=4000,
            serverSelectionTimeoutMS=5000,
            tlsAllowInvalidCertificates=self._mongodb_config.tls_allow_invalid_certificates,
        )
        try:
            await self._client.server_info()
        except pymongo.errors.ServerSelectionTimeoutError as e:
            logger.debug("Failed to connect to MongoDB.", exc_info=True)
            if "Connection refused" in str(e):
                logger.critical(
                    "Failed to connect to MongoDB. Is it running? Make sure your MongoDB connection URI is correct."
                )
            elif "connection closed" in str(e):
                logger.critical(
                    "Failed to connect to MongoDB. "
                    "Your IP may not be whitelisted to access the database. "
                    " Make sure to whitelist all IP addresses that will be connecting "
                    "to the database or whitelist '0.0.0.0/0'."
                )
            # Does this belong here? Or is this a different exception.
            elif "CERTIFICATE_VERIFY_FAILED" in str(e):
                if os.name == "darwin":
                    # MacOS user may need to install certificates.
                    logger.critical(
                        "Failed to connect to MongoDB. Check there's no proxies blocking SSL cert verification. "
                        "Try updating your CA certificates by `cd` to your Python directory "
                        "then run `Install Certificates.command` or run `pip3 install --upgrade certifi`. "
                        "If you are using a self-signed certificate, "
                        "set `tls_allow_invalid_certificates` to `true` in your config."
                    )
                else:
                    logger.critical(
                        "Failed to connect to MongoDB. Check there's no proxies blocking SSL cert verification. "
                        "If you are using a self-signed certificate, "
                        "set `tls_allow_invalid_certificates` to `true` in your config."
                    )
            else:
                logger.critical(
                    "An unknown error occurred while connecting to MongoDB. Check your MongoDB server is reachable. "
                    "Please report this error to the Modmail team."
                )
                logger.critical("Error: %s", e)
            raise DatabaseConnectionError from e
        except pymongo.errors.OperationFailure as e:
            logger.debug("Failed to connect to MongoDB.", exc_info=True)
            if "authentication failed" in str(e):
                logger.critical(
                    "Failed to connect to MongoDB. Invalid credentials. "
                    "Make sure you're using the correct username and password for your database, "
                    "and the password must be escaped according to RFC 3986."
                )
            else:
                logger.critical(
                    "An unknown error occurred while connecting to MongoDB. Check your MongoDB server is reachable. "
                    "Please report this error to the Modmail team."
                )
                logger.critical("Error: %s", e)
            raise DatabaseConnectionError from e
        except Exception as e:
            logger.debug("Failed to connect to MongoDB.", exc_info=True)
            logger.critical(
                "An unknown error occurred while connecting to MongoDB. Check your MongoDB server is reachable. "
                "Please report this error to the Modmail team."
            )
            logger.critical("Error: %s", e)
            raise DatabaseConnectionError from e

        await init_beanie(
            database=self._client.get_database(self.db_name),
            document_models=[MongoDBSettingsDocument, MongoDBPermissionGroupDocument],
        )
        logger.debug("Connected to MongoDB.")
        await self._startup_setup()

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            logger.debug("Disconnected from MongoDB.")

    async def _startup_setup(self) -> None:
        """
        Perform any startup setup required for the database client (migrations, load settings).
        """

        loop = asyncio.get_running_loop()

        logger.debug("Running database migrations.")

        with ProcessPoolExecutor() as pool:
            # Run the migration in a separate process due to beanie's global overrides during migration.
            await loop.run_in_executor(
                pool, do_migration, self._mongodb_config.uri.get_secret_value(), self._mongodb_config.database
            )

        # Load settings from MongoDB
        settings_document = await MongoDBSettingsDocument.find_one(
            MongoDBSettingsDocument.bot_id == self._config.bot.bot_id
        )
        if settings_document is None:
            logger.debug("Settings not found in MongoDB. Creating new settings.")
            settings_document = MongoDBSettingsDocument(bot_id=self._config.bot.bot_id)
            await settings_document.create()

        self._settings_document = settings_document
        logger.debug("Loaded settings from MongoDB.")

        await self._sync_permission_groups()

    async def update_settings(self, **kwargs: Any) -> None:
        # Validate the kwargs, by creating a new Settings object with the provided kwargs.
        # Uses a new Settings model to avoid modifying the original settings and validate the new settings.
        new_settings_model = Settings(
            **self.settings_model.model_dump(exclude={key: True for key in kwargs.keys()}), **kwargs
        )
        settings_dict = new_settings_model.model_dump(
            include={key: True for key in kwargs.keys()} | {"bot_id": True}
        )

        logger.debug("Updating settings in MongoDB: %s", settings_dict)
        assert settings_dict.pop("bot_id") == self._config.bot.bot_id, "Bot ID mismatch."

        settings_document = self._settings_document.model_copy(deep=True)
        for key, value in settings_dict.items():
            if key == "activity" and value is not None:  # if activity is None, no need for conversion
                # Convert the activity to a MongoDBActivityModel
                value = MongoDBActivityModel(**value)
            setattr(settings_document, key, value)

        # noinspection PyArgumentList
        await settings_document.replace()  # Use .replace() to update the document in place
        self._settings_document = settings_document  # Update the settings model to the new one

    async def _sync_permission_groups(self) -> None:
        """
        Sync the permission groups from the database to the local cache.
        """
        self.__permission_groups.clear()
        async for group in MongoDBPermissionGroupDocument.find(
            MongoDBPermissionGroupDocument.bot_id == self._config.bot.bot_id
        ):
            group_key = PermissionGroupKey(group.group_id, group.group_type)
            self.__permission_groups[group_key] = (group, PermissionGroup.model_validate(group))
        logger.debug("Synced %d permission groups from MongoDB.", len(self.__permission_groups))

    def get_permission_group(self, group_id: int, group_type: PermissionGroupType) -> PermissionGroup | None:
        group_key = PermissionGroupKey(group_id, group_type)
        if group_key in self.__permission_groups:
            return self.__permission_groups[group_key][1]
        return None

    async def update_permission_group(self, perm_group: PermissionGroup) -> None:
        group_key = PermissionGroupKey(perm_group.group_id, perm_group.group_type)
        permission_group_dict = perm_group.model_dump(exclude={"group_id", "group_type"})

        assert permission_group_dict.pop("bot_id") == self._config.bot.bot_id, "Bot ID mismatch."

        if group_key in self.__permission_groups:
            # Update the existing permission group
            group = self.__permission_groups[group_key][0].model_copy(deep=True)
            for key, value in permission_group_dict.items():
                setattr(group, key, value)

            # noinspection PyArgumentList
            await group.replace()
            self.__permission_groups[group_key] = (group, PermissionGroup.model_validate(group))
            logger.debug("Updated permission group %s in MongoDB.", group_key)
        else:

            # Create a new permission group
            group = MongoDBPermissionGroupDocument(
                bot_id=self._config.bot.bot_id,
                group_id=perm_group.group_id,
                group_type=perm_group.group_type,
                **permission_group_dict,
            )
            await group.create()
            self.__permission_groups[group_key] = (group, PermissionGroup.model_validate(group))
            logger.debug("Created new permission group %s in MongoDB.", group_key)

    async def delete_permission_group(self, group_id: int, group_type: PermissionGroupType) -> None:
        group_key = PermissionGroupKey(group_id, group_type)
        self.__permission_groups.pop(group_key, None)  # Remove from local cache
        await MongoDBPermissionGroupDocument.find(
            MongoDBPermissionGroupDocument.bot_id == self._config.bot.bot_id
            and MongoDBPermissionGroupDocument.group_id == group_id
            and MongoDBPermissionGroupDocument.group_type == group_type
        ).delete()
        logger.debug("Deleted permission group %s from MongoDB.", group_key)
