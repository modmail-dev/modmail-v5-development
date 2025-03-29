"""Configuration model for the logging system used by the Modmail bot.

This module defines the logging configuration structure with validation logic
to ensure logging levels and formats are correctly specified, and checks for
write permissions on the logfile.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, NonNegativeInt, field_validator

__all__ = [
    "LoggingConfig",
]


class LoggingConfig(BaseModel):
    """Configuration model for the logging system.

    Attributes:
        enabled: Whether logging is enabled.
        root_level: The root logging level.
        console_level: The console logging level.
        logfile_level: The logfile logging level.
        stdout_format: The format for stdout logging.
        logfile: The path to the logfile. If None, file logging is disabled.
        logfile_format: The format for logfile logging.
        logfile_max_size: The maximum size of the logfile in bytes.
        logfile_backup_count: The number of backup logfiles to keep.
        discord_level: The logging level for discord module.
        discord_state_level: The logging level for discord.state module.
        discord_http_level: The logging level for discord.http module.
        discord_gateway_level: The logging level for discord.gateway module.
    """

    enabled: bool = True
    root_level: int = logging.DEBUG
    console_level: int = logging.INFO
    logfile_level: int = logging.DEBUG
    stdout_format: str = "%(message)s"
    logfile: str | None = "modmail.log"
    logfile_format: str = "%(asctime)s %(levelname)s %(name)s:%(lineno)d %(message)s"
    logfile_max_size: NonNegativeInt = 1024 * 1024 * 10  # 10 MB
    logfile_backup_count: NonNegativeInt = 3
    discord_level: int = logging.INFO
    discord_state_level: int = logging.INFO
    discord_http_level: int = logging.INFO
    discord_gateway_level: int = logging.INFO

    @field_validator(
        "root_level",
        "console_level",
        "logfile_level",
        "discord_level",
        "discord_state_level",
        "discord_http_level",
        "discord_gateway_level",
        mode="before",
    )
    @classmethod
    def normalize_level_text(cls, v: str | int) -> int:
        """Normalize the text representation of log levels to their integer values.

        Args:
            v: The logging level as string or int to be normalized.

        Returns:
            int: The normalized integer logging level.

        Raises:
            ValueError: If the provided level is not a valid logging level.
        """
        name_mapping = {
            "CRITICAL": logging.CRITICAL,
            "FATAL": logging.FATAL,
            "ERROR": logging.ERROR,
            "WARNING": logging.WARNING,
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG,
            "NOTSET": logging.NOTSET,
        }
        if isinstance(v, int) or v.isdigit():
            if int(v) in name_mapping.values():
                return int(v)
        else:
            if v.upper() in name_mapping:
                return name_mapping[v.upper()]
        raise ValueError(f"Invalid logging level: {v}. Valid options: DEBUG, INFO, WARNING, ERROR, CRITICAL.")

    @field_validator("stdout_format", "logfile_format")
    @classmethod
    def check_formatting_specifiers(cls, v: str) -> str:
        """Validate that the log format specifiers are correctly formatted.

        Args:
            v: The format string to validate.

        Returns:
            str: The validated format string.

        Raises:
            ValueError: If the format specifiers are invalid.
        """
        try:
            logging.Formatter(v)
        except ValueError as e:
            raise ValueError(f"Invalid formatting specifiers: {e}.") from e
        return v

    @field_validator("logfile")
    @classmethod
    def check_logfile_write_permissions(cls, v: str | None) -> str | None:
        """Verify that the specified logfile can be written to.

        Args:
            v: The path to the logfile as a string, or None to disable file logging.

        Returns:
            str or None: The validated logfile path or None.

        Raises:
            ValueError: If the logfile cannot be written to due to permissions,
                path validity issues, or if the path points to a directory.
        """
        if not v:
            return None
        try:
            with Path(v).open("a", encoding="utf-8"):
                pass
        except IsADirectoryError as e:
            raise ValueError(
                "Logfile path is referencing a directory, please specify a valid file location (e.g. modmail.log)."
            ) from e
        except PermissionError as e:
            raise ValueError(f"No permissions to open the file at {v} (or the path is invalid).") from e
        except OSError as e:
            raise ValueError(f"Logfile cannot be written to: {e}.") from e
        return v

    def is_logfile_enabled(self) -> bool:
        """Determine if logging to a file is enabled.

        Returns:
            bool: True if the logfile is enabled (not None), False otherwise.
        """
        return self.logfile is not None
