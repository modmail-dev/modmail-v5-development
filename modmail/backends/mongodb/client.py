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

from ... import __version__
from ...errors import DatabaseConnectionError
from ..abc import DBClientBase
from .migration import do_migration
from .models import Settings

if TYPE_CHECKING:
    from ...config.models import Config

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
        """
        Initialize the MongoDB client.
        :param config: The full configuration object.
        """

        super().__init__(config)
        assert self._config.mongodb_config is not None, "MongoDB config is not set."
        self.uri = self._config.mongodb_config.uri
        self.db_name = self._config.mongodb_config.database
        self._client: AsyncIOMotorClient[dict[str, Any]] | None = None
        self._settings: Settings | None = None

    @property
    def settings(self) -> Settings:
        assert self._settings is not None, "Settings not loaded."
        return self._settings

    @settings.setter
    def settings(self, settings: Settings) -> None:
        self._settings = settings

    async def connect(self) -> None:
        logger.debug("Connecting to MongoDB...")
        assert self._config.mongodb_config is not None, "MongoDB config is not set."
        self._client = AsyncIOMotorClient(
            self.uri,
            connectTimeoutMS=4000,
            serverSelectionTimeoutMS=5000,
            tlsAllowInvalidCertificates=self._config.mongodb_config.tls_allow_invalid_certificates,
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

        await init_beanie(database=self._client.get_database(self.db_name), document_models=[Settings])
        logger.debug("Connected to MongoDB.")
        await self._startup_setup()

    async def disconnect(self) -> None:
        logger.debug("Disconnecting from MongoDB...")
        if self._client:
            self._client.close()
            self._client = None
        logger.debug("Disconnected from MongoDB.")

    async def _startup_setup(self) -> None:
        """
        Perform any startup setup required for the database client (migrations, load settings).
        """

        loop = asyncio.get_running_loop()

        logger.debug("Running migration...")
        assert self._config.mongodb_config is not None, "MongoDB config is not set."

        with ProcessPoolExecutor() as pool:
            # Run the migration in a separate process due to beanie's global overrides during migration.
            await loop.run_in_executor(
                pool, do_migration, self._config.mongodb_config.uri, self._config.mongodb_config.database
            )

        # Load settings from MongoDB
        self._settings = await Settings.find_one(Settings.bot_id == self._config.bot.bot_id)
        if self._settings is None:
            logger.debug("Settings not found in MongoDB. Creating new settings.")
            self._settings = Settings(bot_id=self._config.bot.bot_id)
            await self._settings.create()

        logger.debug("Loaded settings from MongoDB.")

    async def get_last_ran_version(self) -> str | None:
        return self.settings.last_ran_version

    async def update_last_ran_version(self) -> None:
        logger.debug("Updating last ran version to %s", __version__)
        self.settings.last_ran_version = __version__
        # noinspection PyArgumentList
        await self.settings.save()
