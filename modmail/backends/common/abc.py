"""
modmail.backends.common.abc
===========================
This module defines the abstract base class for database clients used by the Modmail bot.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from .models import Settings

if TYPE_CHECKING:
    from modmail.config import Config

__all__ = [
    "DBClientBase",
]


class DBClientBase(ABC):
    def __init__(self, config: Config):
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
