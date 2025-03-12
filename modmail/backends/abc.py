"""
modmail.backends.abc
====================
This module defines the abstract base class for database clients used by the Modmail bot.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config.models import Config

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
    async def get_last_ran_version(self) -> str | None:
        """
        Get the last ran version of the bot.

        :return: The last ran version of the bot, or None if running for the first time.
        """
        pass

    @abstractmethod
    async def update_last_ran_version(self) -> None:
        """
        Update the last ran version of the bot to the current version.
        """
        pass
