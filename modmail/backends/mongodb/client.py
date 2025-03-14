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

from modmail import __version__
from modmail.backends import DBClientBase, Settings
from modmail.errors import DatabaseConnectionError

from .migration import do_migration
from .models import MongoDBSettingsModel

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
        self.__settings: MongoDBSettingsModel | None = None
        self.__settings_model: Settings | None = None

    @property
    def _settings(self) -> MongoDBSettingsModel:
        assert self.__settings is not None, "Settings not loaded."
        return self.__settings

    @_settings.setter
    def _settings(self, settings: MongoDBSettingsModel) -> None:
        self.__settings = settings
        self.__settings_model = Settings.model_validate(settings)

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

        await init_beanie(database=self._client.get_database(self.db_name), document_models=[MongoDBSettingsModel])
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
        self.__settings = await MongoDBSettingsModel.find_one(
            MongoDBSettingsModel.bot_id == self._config.bot.bot_id
        )
        if self.__settings is None:
            logger.debug("Settings not found in MongoDB. Creating new settings.")
            self.__settings = MongoDBSettingsModel(bot_id=self._config.bot.bot_id)
            await self.__settings.create()

        logger.debug("Loaded settings from MongoDB.")

    async def get_last_ran_version(self) -> str | None:
        return self._settings.last_ran_version

    async def update_last_ran_version(self) -> None:
        logger.debug("Updating last ran version to %s", __version__)
        self._settings.last_ran_version = __version__
        # noinspection PyArgumentList
        await self._settings.save()
