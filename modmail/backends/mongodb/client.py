"""MongoDB client implementation for the Modmail bot.

This module provides functionality to connect to a MongoDB database, handle connection
errors, and perform database operations required by the Modmail bot.
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING, Any, Literal, cast, overload

import pymongo.errors
from beanie import init_beanie  # pyright: ignore [reportUnknownVariableType]
from motor.motor_asyncio import AsyncIOMotorClient

from modmail.enum import ProfileKey, ProfileType, ThreadStatus
from modmail.errors import DatabaseConnectionError, ThreadCreationError, ThreadRecipientOccupiedError
from modmail.utils import MultiKeyCollection

from ..common import DBClientBase, ProfileModel, SettingsModel, ThreadMessageModel, ThreadModel
from .convert import thread_message_model_to_document, thread_model_to_document
from .migration import do_migration
from .models import (
    MongoDBActivityModel,
    MongoDBProfileDocument,
    MongoDBSettingsDocument,
    MongoDBThreadDocument,
    MongoDBThreadMessageDocument,
    MongoDBThreadUserDocument,
)

if TYPE_CHECKING:
    from modmail.config.models import Config, MongoDBDatabaseConfig

__all__ = ["MongoDBClient"]

logger = logging.getLogger(__name__)


class MongoDBClient(DBClientBase):
    """MongoDB client wrapper for Modmail database operations.

    This class provides a simple interface for connecting to a MongoDB database
    and performing all database operations required by the Modmail bot, including
    settings management and profile handling.
    """

    _document_models = [
        MongoDBSettingsDocument,
        MongoDBProfileDocument,
        MongoDBThreadDocument,
        MongoDBThreadUserDocument,
        MongoDBThreadMessageDocument,
    ]

    def __init__(self, config: Config) -> None:
        """Initialize the MongoDB client.

        Args:
            config: The bot configuration containing MongoDB connection details.
        """
        super().__init__(config)
        self.db_name = self._mongodb_config.database
        self._client: AsyncIOMotorClient[dict[str, Any]] | None = None

        # the loaded settings model from the database
        self.__settings_document: MongoDBSettingsDocument | None = None
        self.__settings_model: SettingsModel | None = None  # a read-only view of the settings model

        # Profiles and threads are cached from the database on startup.
        self.__profiles_cache: dict[ProfileKey, tuple[MongoDBProfileDocument, ProfileModel]] = {}
        self.__open_threads_cache = MultiKeyCollection[MongoDBThreadDocument]("key", "channel_id")

    @property
    def _settings_document(self) -> MongoDBSettingsDocument:
        """Get the MongoDB settings document.

        Returns:
            The current settings document.
        """
        assert self.__settings_document is not None, "Settings not loaded."
        return self.__settings_document

    @_settings_document.setter
    def _settings_document(self, settings_document: MongoDBSettingsDocument) -> None:
        """Set the MongoDB settings document and update the settings model.

        Args:
            settings_document: The MongoDB settings document to set.
        """
        self.__settings_document = settings_document
        self.__settings_model = SettingsModel.model_validate(settings_document)

    @property
    def settings_model(self) -> SettingsModel:
        """Get the current settings model.

        Returns:
            The current validated settings model.
        """
        assert self.__settings_model is not None, "Settings model not loaded."
        return self.__settings_model

    @property
    def profiles(self) -> list[ProfileModel]:
        """Get the list of profiles from the cache.

        Returns:
            A list of profiles.
        """
        return [profile_model for _, profile_model in self.__profiles_cache.values()]

    @property
    def _mongodb_config(self) -> MongoDBDatabaseConfig:
        """Get the MongoDB configuration.

        Returns:
           The MongoDB configuration.
        """
        assert self._config.mongodb_config is not None, "MongoDB config is not set."
        return self._config.mongodb_config

    async def connect(self) -> None:
        """Connect to the MongoDB database.

        Establishes connection to MongoDB and initializes the database client.

        Raises:
            DatabaseConnectionError: If connection to MongoDB fails for any reason.
        """
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
                    "Failed to connect to MongoDB. Is it running? "
                    "Make sure your MongoDB connection URI is correct."
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
                    "An unknown error occurred while connecting to MongoDB. Check your MongoDB server "
                    "is reachable. Please report this error to the Modmail team."
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
                    "An unknown error occurred while connecting to MongoDB. Check your MongoDB server "
                    "is reachable. Please report this error to the Modmail team."
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
            document_models=self._document_models,
        )
        logger.debug("Connected to MongoDB.")
        await self._startup_setup()

    async def disconnect(self) -> None:
        """Disconnect from the MongoDB database.

        Closes the connection to the MongoDB database if a connection exists.
        """
        if self._client:
            self._client.close()
            self._client = None
            logger.debug("Disconnected from MongoDB.")

    async def _startup_setup(self) -> None:
        """Perform database startup operations.

        Executes required database operations during startup, including:
        - Running pending migrations.
        - Loading or creating bot settings.
        - Syncing profiles from the database to the local cache.
        """
        loop = asyncio.get_running_loop()

        logger.debug("Running database migrations.")

        with ProcessPoolExecutor() as pool:
            # Run the migration in a separate process due to beanie's global overrides during migration.
            await loop.run_in_executor(
                pool, do_migration, self._mongodb_config.uri.get_secret_value(), self._mongodb_config.database
            )

        await self.sync_settings()
        await self.sync_profiles()
        await self.sync_open_threads()

    async def sync_settings(self) -> None:
        """Synchronize settings with the database.

        This method is called to ensure that the current settings model
        are up to date with the settings in the database.
        If the settings document is not found, it creates a new one.
        """
        settings_document = await MongoDBSettingsDocument.find_one(
            MongoDBSettingsDocument.bot_id == self._config.bot.bot_id
        )
        if settings_document is None:
            logger.debug("Settings not found in MongoDB. Creating new settings.")
            settings_document = MongoDBSettingsDocument(bot_id=self._config.bot.bot_id)
            # noinspection PyArgumentList
            await settings_document.insert()

        self._settings_document = settings_document
        logger.debug("Synced settings from MongoDB.")

    async def update_settings(self, **kwargs: Any) -> None:
        """Update bot settings in the database.

        Updates specific settings fields in the database while validating the changes.

        Args:
            **kwargs: Key-value pairs of settings to update.

        Raises:
            DatabaseConnectionError: If the update operation fails.
        """
        # Validate the kwargs, by creating a new Settings object with the provided kwargs.
        # Uses a new Settings model to avoid modifying the original settings and validate the new settings.
        new_settings_model = SettingsModel(
            **self.settings_model.model_dump(exclude=dict.fromkeys(kwargs, True)), **kwargs
        )
        settings_dict = new_settings_model.model_dump(include=dict.fromkeys(kwargs, True) | {"bot_id": True})

        logger.debug("Updating settings in MongoDB: %s", settings_dict)
        assert settings_dict.pop("bot_id") == self._config.bot.bot_id, "Bot ID mismatch."

        settings_document = self._settings_document.model_copy(deep=True)
        for key, value in settings_dict.items():
            if key == "activity" and value is not None:  # if activity is None, no need for conversion
                # Convert the activity to a MongoDBActivityModel
                value = MongoDBActivityModel(**value)
            setattr(settings_document, key, value)

        try:
            # noinspection PyArgumentList
            await settings_document.replace()  # Use .replace() to update the document in place
        except Exception as e:
            logger.error("Failed to update settings in MongoDB: %s", e)
            raise DatabaseConnectionError from e
        self._settings_document = settings_document  # Update the settings model to the new one

    async def sync_profiles(self) -> None:
        """Sync profiles from the database to the local cache.

        Retrieves all profiles from the database for the current bot and
        stores them in the local cache for faster access.
        """
        profiles_cache: dict[ProfileKey, tuple[MongoDBProfileDocument, ProfileModel]] = {}
        # Finds all profiles in the database and adds them to the cache.
        async for profile_document in MongoDBProfileDocument.find(
            MongoDBProfileDocument.bot_id == self._config.bot.bot_id
        ):
            profile_key = ProfileKey(profile_document.profile_id, profile_document.profile_type)
            profiles_cache[profile_key] = (profile_document, ProfileModel.model_validate(profile_document))

        self.__profiles_cache = profiles_cache
        logger.debug("Synced %d profiles from MongoDB.", len(self.__profiles_cache))

    def get_profile(self, profile_id: int, profile_type: ProfileType) -> ProfileModel | None:
        """Get a profile from the cache.

        Retrieves a profile from the local cache based on ID and type.

        Args:
            profile_id: The ID of the profile to retrieve.
            profile_type: The type of the profile to retrieve.

        Returns:
            The profile model if found, None otherwise.
        """
        profile_key = ProfileKey(profile_id, profile_type)
        if profile_key in self.__profiles_cache:
            return self.__profiles_cache[profile_key][1]
        return None

    async def update_profile(self, profile: ProfileModel) -> None:
        """Update or create a profile in the database.

        Updates an existing profile or creates a new one if it doesn't exist.

        Args:
            profile: The profile to update or create.
        """
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
            self.__profiles_cache[profile_key] = (new_profile, ProfileModel.model_validate(new_profile))
            logger.debug("Updated profile %s in MongoDB.", profile_key)
        else:
            # Create a new profile
            new_profile = MongoDBProfileDocument(
                bot_id=self._config.bot.bot_id,
                profile_id=profile.profile_id,
                profile_type=profile.profile_type,
                **new_profile_dict,
            )
            # noinspection PyArgumentList
            await new_profile.insert()
            self.__profiles_cache[profile_key] = (new_profile, ProfileModel.model_validate(new_profile))
            logger.debug("Created new profile %s in MongoDB.", profile_key)

    async def delete_profile(self, profile_id: int) -> None:
        """Delete a profile from the database and cache.

        Removes all profiles with the specified ID from both the database and local cache.

        Args:
            profile_id: The ID of the profile to delete.
        """
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

    # THREADS

    async def sync_open_threads(self) -> None:
        """Sync open threads from the database to the local cache."""
        open_threads_cache = MultiKeyCollection[MongoDBThreadDocument]("key", "channel_id")

        async for thread_document in MongoDBThreadDocument.find(
            MongoDBThreadDocument.bot_id == self._config.bot.bot_id
            and MongoDBThreadDocument.status == ThreadStatus.open,
            fetch_links=True,
        ):
            open_threads_cache.add(thread_document, key=thread_document.key, channel_id=thread_document.channel_id)

        self.__open_threads_cache = open_threads_cache
        logger.debug("Synced %d open threads from MongoDB.", len(self.__open_threads_cache))

    async def get_open_threads(self) -> list[ThreadModel]:
        """Get the list of open threads from the cache.

        Returns:
            A list of open threads.
        """
        return await asyncio.gather(*[
            thread_document.get_model() for thread_document in self.__open_threads_cache
        ])

    async def create_thread(self, thread: ThreadModel) -> None:
        """Create a new thread in the database.

        Args:
            thread: The thread model to create.

        Raises:
            ThreadCreationError: If a thread with a duplicate key or channel.
            ThreadRecipientOccupiedError: If a thread with the same recipient already exists.
        """
        # Check if the thread has conflicting channel or recipients.
        for thread_document in self.__open_threads_cache:
            # Fetch all links for the thread document to ensure recipients are populated.
            if thread_document.recipients and not isinstance(
                thread_document.recipients[0], MongoDBThreadUserDocument
            ):
                await thread_document.fetch_all_links()
                logger.debug(
                    "[yellow]Fetched all links for thread %s in create_thread, "
                    "links should be prefetched instead.",
                    thread_document.key,
                    extra={"markup": True},
                )

            if thread_document.channel_id == thread.channel_id:
                raise ThreadCreationError("Thread with this channel ID already exists.")
            if any(
                new_recipient.user_id == cast(MongoDBThreadUserDocument, old_recipient).id
                for old_recipient in thread_document.recipients
                for new_recipient in thread.recipients
            ):
                raise ThreadRecipientOccupiedError("An open thread with this recipient already exists.")

        # Create the thread in the database.
        thread_document = await thread_model_to_document(thread)
        # TODO: Handle key collision.
        # noinspection PyArgumentList
        await thread_document.insert()
        if thread.status == ThreadStatus.open:
            self.__open_threads_cache.add(
                thread_document, key=thread_document.key, channel_id=thread_document.channel_id
            )
        logger.info("Created thread %s for %s.", thread.key, thread.recipients)

    async def get_thread_by_channel(self, channel_id: int, *, only_open: bool = True) -> ThreadModel | None:
        """Get a thread by channel ID.

        Args:
            channel_id: The channel ID of the thread to retrieve.
            only_open: Whether to only search for open threads.

        Returns:
            The thread model if found, None otherwise.
        """
        if only_open:
            # Open threads are always cached.
            thread_document = self.__open_threads_cache.get(channel_id=channel_id)
            if thread_document is not None:
                return await thread_document.get_model()
            return None

        thread_document = await MongoDBThreadDocument.find_one(
            MongoDBThreadDocument.bot_id == self._config.bot.bot_id
            and MongoDBThreadDocument.channel_id == channel_id,
            fetch_links=True,
        )
        if thread_document is not None:
            return await thread_document.get_model()
        return None

    async def get_thread_by_key(self, key: str, *, only_open: bool = True) -> ThreadModel | None:
        """Get a thread by its key.

        Args:
            key: The key of the thread to retrieve.
            only_open: Whether to only search for open threads.

        Returns:
            The thread model if found, None otherwise.
        """
        if only_open:
            # Open threads are always cached.
            thread_document = self.__open_threads_cache.get(key=key)
            if thread_document is not None:
                return await thread_document.get_model()
            return None

        thread_document = await MongoDBThreadDocument.find_one(
            MongoDBThreadDocument.bot_id == self._config.bot.bot_id and MongoDBThreadDocument.key == key,
            fetch_links=True,
        )
        if thread_document is not None:
            return await thread_document.get_model()
        return None

    async def get_thread_by_recipient(self, recipient_id: int) -> ThreadModel | None:
        """Get an open thread by recipient ID.

        Args:
            recipient_id: The recipient ID of the thread to retrieve.

        Returns:
            The thread model if found, None otherwise.
        """
        for thread_document in self.__open_threads_cache:
            await thread_document.fetch_all_links()
            # Check if the recipient ID is in the thread's recipients.
            if any(
                cast(MongoDBThreadUserDocument, recipient).id == recipient_id
                for recipient in thread_document.recipients
            ):
                return await thread_document.get_model()
        return None

    @overload
    async def get_all_threads_by_recipient(self, recipient_id: int, count: Literal[True] = True) -> int: ...

    @overload
    async def get_all_threads_by_recipient(
        self, recipient_id: int, count: Literal[False] = False
    ) -> list[ThreadModel]: ...

    async def get_all_threads_by_recipient(
        self, recipient_id: int, count: bool = False
    ) -> int | list[ThreadModel]:
        """Get all threads by recipient ID.

        Args:
            recipient_id: The recipient ID of the threads to retrieve.
            count: Whether to return only the count of threads.

        Returns:
            A list of thread models associated with the recipient or the count of threads if count is True.
        """
        if count:
            return await MongoDBThreadDocument.find(
                MongoDBThreadDocument.bot_id == self._config.bot.bot_id
                and cast(MongoDBThreadUserDocument, MongoDBThreadDocument.recipients).id == recipient_id,
                fetch_links=True,
            ).count()

        thread_documents = await MongoDBThreadDocument.find(
            MongoDBThreadDocument.bot_id == self._config.bot.bot_id
            and cast(MongoDBThreadUserDocument, MongoDBThreadDocument.recipients).id == recipient_id,
            fetch_links=True,
        ).to_list()
        return await asyncio.gather(*[thread_document.get_model() for thread_document in thread_documents])

    async def save_message(self, thread_message: ThreadMessageModel) -> None:
        """Save a thread message to the database.

        Args:
            thread_message: The thread message model to save.

        Raises:
            DatabaseConnectionError: If the save operation fails.
        """
        thread_document = await self.get_thread_by_key(thread_message.thread_key)
        if thread_document is None:
            logger.error("Thread %s not found in database.", thread_message.thread_key)
            return

        # Create the thread message document.
        thread_message_document = await thread_message_model_to_document(thread_message)

        # Save the thread message document.
        try:
            # noinspection PyArgumentList
            await thread_message_document.insert()
        except Exception as e:
            logger.error("Failed to save message in MongoDB: %s", e)
            raise DatabaseConnectionError("Something went wrong while saving the message.") from e
        logger.debug("Saved message %s in thread %s.", thread_message.message_id, thread_message.thread_key)
