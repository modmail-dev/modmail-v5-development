"""Defines the abstract base class for database clients.

This module provides the DBClientBase class outlining the interface
for database operations used by the Modmail bot.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Literal, overload

from modmail.enum import ProfileType, ThreadStatus

if TYPE_CHECKING:
    from modmail.config import Config

    from .models import ProfileModel, SettingsModel, ThreadMessageModel, ThreadModel, ThreadUserModel

__all__ = ["DBClientBase"]


class DBClientBase(ABC):  # pragma: no cover
    """Abstract base class for database clients.

    This class outlines the necessary interface for database operations within the Modmail bot.
    """

    def __init__(self, config: Config) -> None:
        """Initializes the database client.

        Args:
            config: The configuration object containing database settings.
        """
        self._config = config

    @property
    @abstractmethod
    def settings_model(self) -> SettingsModel:
        """Gets the settings model class.

        Returns:
            The settings model.
        """

    @property
    @abstractmethod
    def profiles(self) -> list[ProfileModel]:
        """Gets the list of profiles.

        Returns:
            A list of profile objects.
        """

    @abstractmethod
    async def connect(self) -> None:
        """Connects to the database and loads bot settings.

        Raises:
            DatabaseConnectionError: If the connection to the database fails.
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnects from the database."""

    @abstractmethod
    async def update_settings(self, **kwargs: Any) -> None:
        """Updates settings in the database.

        Args:
            **kwargs: Arbitrary keyword arguments representing setting keys and their new values.
        """

    @abstractmethod
    async def sync_settings(self) -> None:
        """Synchronizes the settings with the database.

        This method shouldn't need to be called directly, as the bot stores the settings in cache.
        """

    @abstractmethod
    async def sync_profiles(self) -> None:
        """Synchronizes the profiles with the database.

        This method shouldn't need to be called directly, as the bot stores the profiles in cache.
        """

    @abstractmethod
    async def sync_open_threads(self) -> None:
        """Synchronizes the open threads with the database.

        This method shouldn't need to be called directly, as the bot stores the threads in cache.
        """

    @abstractmethod
    def get_profile(self, profile_id: int, profile_type: ProfileType) -> ProfileModel | None:
        """Retrieves a profile from the database cache.

        Args:
            profile_id: The identifier of the profile.
            profile_type: The type of the profile (e.g., user/role).

        Returns:
            The profile if found, otherwise None.
        """

    @abstractmethod
    async def update_profile(self, profile: ProfileModel) -> None:
        """Updates or creates a profile in the database.

        Args:
            profile: The profile object to update or create.
        """

    @abstractmethod
    async def delete_profile(self, profile_id: int) -> None:
        """Deletes a profile from the database.

        Args:
            profile_id: The identifier of the profile to delete.
        """

    @abstractmethod
    async def get_open_threads(self) -> list[ThreadModel]:
        """Retrieves all open threads from the database.

        Returns:
            A list of open threads.
        """

    @abstractmethod
    async def get_thread_by_recipient(self, recipient_id: int) -> ThreadModel | None:
        """Retrieves an open thread by recipient ID.

        If you want to get closed threads as well, use `get_all_threads_by_recipient` instead.

        Args:
            recipient_id: The identifier of the recipient.

        Returns:
            The thread if found, otherwise None.
        """

    @overload
    async def get_all_threads_by_recipient(
        self, recipient_id: int, *, count: Literal[True] = True, only_closed: bool = False
    ) -> int: ...

    @overload
    async def get_all_threads_by_recipient(
        self, recipient_id: int, *, count: Literal[False] = False, only_closed: bool = False
    ) -> list[ThreadModel]: ...

    @abstractmethod
    async def get_all_threads_by_recipient(
        self, recipient_id: int, *, count: bool = False, only_closed: bool = False
    ) -> int | list[ThreadModel]:
        """Retrieves all threads by recipient ID.

        Args:
            recipient_id: The identifier of the recipient.
            count: Whether to return the count of threads or the list of thread objects.
            only_closed: Whether to only include closed threads.

        Returns:
            A list of threads associated with the recipient or the count of threads if count is True.
        """

    @abstractmethod
    async def get_thread_by_key(self, key: str, *, only_open: bool = True) -> ThreadModel | None:
        """Retrieves a thread by its key.

        Args:
            key: The key of the thread.
            only_open: Whether to only search for open threads.

        Returns:
            The thread if found, otherwise None.
        """

    @abstractmethod
    async def get_thread_by_channel(self, channel_id: int, *, only_open: bool = True) -> ThreadModel | None:
        """Retrieves a thread by its channel ID.

        Args:
            channel_id: The identifier of the channel.
            only_open: Whether to only search for open threads.

        Returns:
            The thread if found, otherwise None.
        """

    @abstractmethod
    async def create_thread(self, thread: ThreadModel) -> None:
        """Creates a new thread in the database.

        Args:
            thread: The thread object to create.

        Raises:
            ThreadRecipientOccupiedError: If the recipient is already in another open thread.
        """

    @abstractmethod
    async def save_message(self, thread_message: ThreadMessageModel) -> None:
        """Saves a message to the database.

        Args:
            thread_message: The thread message object to save.

        Raises:
            ThreadNotFoundError: If the thread is not found.
        """

    @abstractmethod
    async def close_thread(
        self,
        thread_key: str,
        closer: ThreadUserModel,
        *,
        thread_status: ThreadStatus = ThreadStatus.closed_by_command,
    ) -> None:
        """Closes a thread in the database.

        Args:
            thread_key: The key of the thread to close.
            closer: The user who is closing the thread.
            thread_status: The status of the thread after closing.

        Raises:
            ThreadNotFoundError: If the thread is not found in the database or isn't currently open.
        """
