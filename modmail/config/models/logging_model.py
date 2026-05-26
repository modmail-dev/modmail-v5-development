"""Configuration model for the logging system."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from pydantic import (
    BaseModel,
    Field,
    NonNegativeInt,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    field_validator,
)

__all__ = [
    "LoggingConfig",
]


class LoggingConfig(
    BaseModel,
    frozen=True,
    str_strip_whitespace=True,
    coerce_numbers_to_str=True,
    use_attribute_docstrings=True,
):
    """Configuration model for the logging system."""

    managed: bool = True
    """Whether the bot manages console logging and log levels."""
    error_only: bool = True
    """Raise all user-configurable logging levels below WARNING to WARNING.
    Useful for hiding informational output from third-party libraries in
    production."""
    modmail_level: int = logging.INFO
    """Console output level for the `modmail` package."""
    root_level: int = logging.WARNING
    """Default console logging level for loggers not listed in the managed
    logger set."""
    discord_level: int = logging.INFO
    """Console output level for the `discord` package."""
    discord_state_level: int = logging.INFO
    """Console output level for `discord.state`."""
    discord_http_level: int = logging.INFO
    """Console output level for `discord.http`."""
    discord_gateway_level: int = logging.INFO
    """Console output level for `discord.gateway`."""
    sqlalchemy_level: int = logging.WARNING
    """Console output level for the `sqlalchemy` package."""
    sqlalchemy_engine_level: int = logging.WARNING
    """Console output level for `sqlalchemy.engine` (raw SQL statements)."""
    pymongo_level: int = logging.WARNING
    """Console output level for the `pymongo` package."""
    pymongo_topology_level: int = logging.WARNING
    """Console output level for `pymongo.topology`."""
    logfile: Path | None = Field(default=Path("logs/modmail.log"), validate_default=True)
    """Path to the logfile. Set to `None` to disable file logging."""
    logfile_format: str = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s"
    """Format string for logfile logging."""
    logfile_max_size: NonNegativeInt = 1024 * 1024 * 10  # 10 MB
    """Maximum size of the logfile in bytes before rotation."""
    logfile_backup_count: NonNegativeInt = 3
    """Number of backup logfiles to keep during rotation."""
    stdout_format: str = "%(message)s"
    """Format string for stdout logging."""

    _LEVEL_FIELDS = frozenset({
        "modmail_level",
        "root_level",
        "discord_level",
        "discord_state_level",
        "discord_http_level",
        "discord_gateway_level",
        "sqlalchemy_level",
        "sqlalchemy_engine_level",
        "pymongo_level",
        "pymongo_topology_level",
    })

    @field_validator(
        *_LEVEL_FIELDS,
        mode="before",
    )
    @classmethod
    def normalize_level_text(cls, v: object) -> int:
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
        if not isinstance(v, int):
            v = str(v).strip()
        if isinstance(v, int) or v.isdigit():
            if int(v) in name_mapping.values():
                return int(v)
        else:
            if v.upper() in name_mapping:
                return name_mapping[v.upper()]
        raise ValueError(
            f"Invalid logging level: {v}. Valid options: NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL."
        )

    @field_validator(*_LEVEL_FIELDS)
    @classmethod
    def clamp_error_only(cls, v: int, info: ValidationInfo) -> int:
        """Clamp logging levels to WARNING if `error_only` is enabled.

        Returns:
            The potentially clamped logging level.
        """
        if info.data["error_only"] and v < logging.WARNING:
            return logging.WARNING
        return v

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

    @field_validator("logfile", mode="wrap")
    @classmethod
    def check_logfile_write_permissions(cls, v: object, handler: ValidatorFunctionWrapHandler) -> Path | None:
        """Verify that the specified logfile can be written to.

        Returns:
            `Path` or `None`: The validated logfile path or `None`.

        Raises:
            ValueError: If the logfile cannot be written to due to permissions,
                path validity issues, or if the path points to a directory.
        """
        if not v:
            v = None

        v = cast("Path | None", handler(v))
        if v is None:
            return None

        try:
            v.parent.mkdir(parents=True, exist_ok=True)
            with v.open("a", encoding="utf-8"):
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
