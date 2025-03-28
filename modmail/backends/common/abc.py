"""
modmail.backends.common.abc
===========================
This module defines the abstract base class for database clients used by the Modmail bot.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modmail.config import Config
    from modmail.enum import ProfileType

    from .models import Profile, Settings

__all__ = [
    "DBClientBase",
]


class DBClientBase(ABC):  # pragma: no cover
    def __init__(self, config: Config) -> None:
        """
        Initialize the database client with the given configuration.

        :param config: The configuration object containing database settings.
        """
        self._config = config

    @property
    @abstractmethod
    def settings_model(self) -> Settings:
        """
        Get the settings model class.
        """
        pass

    @abstractmethod
    async def connect(self) -> None:
        """
        Connect to the database and load the bot settings.

        :raises DatabaseConnectionError: If the connection to the database fails.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the database.
        """
        pass

    @abstractmethod
    async def update_settings(self, **kwargs: Any) -> None:
        """
        Update settings in the database.
        This method updates the specified key=value pairs in the settings.

        :param kwargs: Optional keyword arguments representing the setting keys to update.
        """
        pass

    @abstractmethod
    def get_profile(self, profile_id: int, profile_type: ProfileType) -> Profile | None:
        """
        Retrieves a profile from the database.
        This method does not fetch the profile from the database, but rather returns a cached version.

        :param profile_id: The ID that belongs to a profile.
        :param profile_type: The type of the profile (user/role).
        :return: The profile if found, None otherwise.
        """
        pass

    @abstractmethod
    async def update_profile(self, profile: Profile) -> None:
        """
        Update or create a profile on the database.

        :param profile: The profile to update or create.
        """
        pass

    @abstractmethod
    async def delete_profile(self, profile_id: int) -> None:
        """
        Delete a profile from the database.

        :param profile_id: The ID of the profile.
        """
        pass
