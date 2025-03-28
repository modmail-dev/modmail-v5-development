"""Defines the abstract base class for database clients.

This module provides the DBClientBase class outlining the interface
for database operations used by the Modmail bot.
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
    def settings_model(self) -> Settings:
        """Gets the settings model class.

        Returns:
            The settings model.
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
    def get_profile(self, profile_id: int, profile_type: ProfileType) -> Profile | None:
        """Retrieves a profile from the database cache.

        Args:
            profile_id: The identifier of the profile.
            profile_type: The type of the profile (e.g., user/role).

        Returns:
            The profile if found, otherwise None.
        """

    @abstractmethod
    async def update_profile(self, profile: Profile) -> None:
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
