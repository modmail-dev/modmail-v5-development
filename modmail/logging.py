"""Configuration for the bot's logging system.

This module sets up the logging infrastructure for both the Modmail bot and
discord.py internals. It configures log handlers, formatters, log rotation,
and establishes appropriate log levels based on the application configuration.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

from rich.logging import RichHandler
from rich.text import Text

if TYPE_CHECKING:
    from types import ModuleType

try:
    from . import CONFIG
except ImportError as e:  # pragma: no cover
    raise RuntimeError("Did you forget to first run modmail.init()?") from e

__all__ = ["setup_logging"]

_LOGGING_IS_SETUP = False


class FileFormatter(logging.Formatter):
    """Custom formatter for log files.

    Removes rich markup syntax from log messages when writing to files.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record by removing rich markup if present.

        Args:
            record: The log record to format.

        Returns:
            The formatted log string with markup removed if applicable.
        """
        formatted_str = super().format(record)
        if record.__dict__.get("markup", False):
            # Remove the "[some markup] text [/some markup]" markup for rich.
            formatted_str = Text.from_markup(formatted_str).plain
        return formatted_str


def setup_logging() -> None:
    """Set up logging for the bot and discord.py library.

    Configures both console and file logging with appropriate formatters and handlers.
    Log levels, rotation settings, and formatting are based on the application config.
    Console output uses rich formatting with traceback support, while file output
    uses a plain text format with configurable rotation.
    """
    global _LOGGING_IS_SETUP  # noqa: PLW0603

    if _LOGGING_IS_SETUP:  # Don't set up logging again if it's already done.
        return
    _LOGGING_IS_SETUP = True  # pyright: ignore [reportConstantRedefinition]

    # Configure root logging level.
    project_root_logger = logging.getLogger("modmail")
    project_root_logger.setLevel(CONFIG.logging.root_level)

    # Configure RichHandler for console logging with rich formatting.
    formatter = logging.Formatter(CONFIG.logging.stdout_format)

    # Suppress tracebacks from certain modules for cleaner output.
    import discord

    tracebacks_suppress: list[ModuleType] = [discord]

    try:
        import sqlalchemy

        tracebacks_suppress.append(sqlalchemy)
    except ImportError:
        pass

    try:
        import pymongo

        tracebacks_suppress.append(pymongo)
    except ImportError:
        pass

    handler = RichHandler(
        show_level=True,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        log_time_format=lambda dt: Text(dt.strftime("%X,%f")[:-3]),
        tracebacks_suppress=tracebacks_suppress,
    )
    handler.setFormatter(formatter)
    handler.setLevel(CONFIG.logging.console_level)
    project_root_logger.addHandler(handler)

    # Configure Discord logging
    logger_dc1 = logging.getLogger("discord")
    logger_dc1.setLevel(CONFIG.logging.discord_level)
    logger_dc1.addHandler(handler)

    logger_dc2 = logging.getLogger("discord.state")
    logger_dc2.setLevel(CONFIG.logging.discord_state_level)
    logger_dc2.addHandler(handler)

    logger_dc3 = logging.getLogger("discord.http")
    logger_dc3.setLevel(CONFIG.logging.discord_http_level)
    logger_dc3.addHandler(handler)

    logger_dc4 = logging.getLogger("discord.gateway")
    logger_dc4.setLevel(CONFIG.logging.discord_gateway_level)
    logger_dc4.addHandler(handler)

    # Configure RotatingFileHandler for file logging with rotation.
    if CONFIG.logging.logfile is not None:
        logfile_handler = RotatingFileHandler(
            CONFIG.logging.logfile,
            mode="a",
            maxBytes=CONFIG.logging.logfile_max_size,
            backupCount=CONFIG.logging.logfile_backup_count,
        )
        logfile_handler.setFormatter(FileFormatter(CONFIG.logging.logfile_format))
        logfile_handler.setLevel(CONFIG.logging.logfile_level)
        project_root_logger.addHandler(logfile_handler)
        logger_dc1.addHandler(logfile_handler)

    # TODO: Configure sql + mongodb logging.
