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

from modmail.backends import DBClientBase, Profile, Settings
from modmail.enum import ProfileKey, ProfileType
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

        # Profiles are cached from the database on startup.
        self.__profiles_cache: dict[ProfileKey, tuple[MongoDBProfileDocument, Profile]] = {}

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
            document_models=[MongoDBSettingsDocument, MongoDBProfileDocument],
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

        await self._sync_profiles()

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

    async def _sync_profiles(self) -> None:
        """
        Sync the profiles from the database to the local cache.
        """
        self.__profiles_cache.clear()
        # Finds all profiles in the database and adds them to the cache.
        async for profile_document in MongoDBProfileDocument.find(
            MongoDBProfileDocument.bot_id == self._config.bot.bot_id
        ):
            profile_key = ProfileKey(profile_document.profile_id, profile_document.profile_type)
            self.__profiles_cache[profile_key] = (profile_document, Profile.model_validate(profile_document))
        logger.debug("Synced %d profiles from MongoDB.", len(self.__profiles_cache))

    def get_profile(self, profile_id: int, profile_type: ProfileType) -> Profile | None:
        profile_key = ProfileKey(profile_id, profile_type)
        if profile_key in self.__profiles_cache:
            return self.__profiles_cache[profile_key][1]
        return None

    async def update_profile(self, profile: Profile) -> None:
        profile_key = ProfileKey(profile.profile_id, profile.profile_type)
        new_profile_dict = profile.model_dump(exclude={"profile_id", "profile_type"})

        assert new_profile_dict.pop("bot_id") == self._config.bot.bot_id, "Bot ID mismatch."

        if profile_key in self.__profiles_cache:
            # Update the existing profile
            new_profile = self.__profiles_cache[profile_key][0].model_copy(deep=True)
            for key, value in new_profile_dict.items():
                setattr(new_profile, key, value)

            # noinspection PyArgumentList
            await new_profile.replace()
            self.__profiles_cache[profile_key] = (new_profile, Profile.model_validate(new_profile))
            logger.debug("Updated profile %s in MongoDB.", profile_key)
        else:

            # Create a new profile
            new_profile = MongoDBProfileDocument(
                bot_id=self._config.bot.bot_id,
                profile_id=profile.profile_id,
                profile_type=profile.profile_type,
                **new_profile_dict,
            )
            await new_profile.create()
            self.__profiles_cache[profile_key] = (new_profile, Profile.model_validate(new_profile))
            logger.debug("Created new profile %s in MongoDB.", profile_key)

    async def delete_profile(self, profile_id: int) -> None:
        # Delete the profile from the database.
        await MongoDBProfileDocument.find(
            MongoDBProfileDocument.bot_id == self._config.bot.bot_id
            and MongoDBProfileDocument.profile_id == profile_id
        ).delete()

        # Delete the profile from cache.
        for profile_key in list(self.__profiles_cache.keys()):
            if profile_key.profile_id == profile_id:
                del self.__profiles_cache[profile_key]

        logger.debug("Deleted profile ID=%d from MongoDB.", profile_id)
