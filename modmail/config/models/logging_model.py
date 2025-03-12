"""
modmail.config.models.logging_model
===================================
This module defines the configuration model for the logging system used by the Modmail bot.
It includes validation logic to ensure logging levels and formats are correctly specified,
and checks for write permissions on the logfile.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, NonNegativeInt, field_validator

__all__ = [
    "LoggingConfig",
]


# noinspection PyNestedDecorators
class LoggingConfig(BaseModel):
    """
    Configuration model for the logging system.

    Attributes:
        enabled (bool): Whether logging is enabled. Defaults to True.
        root_level (int): The root logging level. Defaults to logging.DEBUG.
        console_level (int): The console logging level. Defaults to logging.INFO.
        logfile_level (int): The logfile logging level. Defaults to logging.DEBUG.
        stdout_format (str): The format for stdout logging. Defaults to "[%(levelname)s] %(message)s".
        logfile (str | None): The path to the logfile. Defaults to "modmail.log".
        logfile_format (str): The format for logfile logging. Defaults to "%(asctime)s %(levelname)s %(name)s:%(lineno)d %(message)s".
        logfile_max_size (NonNegativeInt): The maximum size of the logfile in bytes. Defaults to 35 MB.
        logfile_backup_count (NonNegativeInt): The number of backup logfiles to keep. Defaults to 0.
        discord_level (int): The logging level for discord. Defaults to logging.DEBUG.
        discord_state_level (int): The logging level for discord.state. Defaults to logging.INFO.
        discord_http_level (int): The logging level for discord.http. Defaults to logging.INFO.
        discord_gateway_level (int): The logging level for discord.gateway. Defaults to logging.INFO.
    """

    enabled: bool = True
    root_level: int = logging.DEBUG
    console_level: int = logging.INFO
    logfile_level: int = logging.DEBUG
    stdout_format: str = "%(message)s"
    logfile: str | None = "modmail.log"
    logfile_format: str = "%(asctime)s %(levelname)s %(name)s:%(lineno)d %(message)s"
    logfile_max_size: NonNegativeInt = 1024 * 1024 * 35  # 35 MB
    logfile_backup_count: NonNegativeInt = 0
    discord_level: int = logging.DEBUG
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
        """
        Normalize the level texts to logging level ints.
        """
        name_mapping = {
            "CRITICAL": logging.CRITICAL,
            "FATAL": logging.FATAL,
            "ERROR": logging.ERROR,
            "WARN": logging.WARN,
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
        """
        Check if the formatting specifiers are valid.
        """
        try:
            logging.Formatter(v)
        except ValueError as e:
            raise ValueError(f"Invalid formatting specifiers: {e}.")
        return v

    @field_validator("logfile")
    @classmethod
    def check_logfile_write_permissions(cls, v: str | None) -> str | None:
        """
        Check if the logfile can be written to.
        """
        if not v:
            return None
        try:
            with open(v, "a"):
                pass
        except IsADirectoryError:
            raise ValueError(
                "Logfile path is referencing a directory, please specify a "
                "valid file location (e.g. modmail.log)."
            )
        except PermissionError:
            raise ValueError(f"No permissions to open the file at {v} (or the path is invalid).")
        except OSError as e:
            raise ValueError(f"Logfile cannot be written to: {e}.")
        return v

    def is_logfile_enabled(self) -> bool:
        """
        Check if the logfile is enabled.
        """
        return self.logfile is not None
