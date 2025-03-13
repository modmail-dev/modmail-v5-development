"""
modmail.logging
===============
This module configures the logging for the bot and discord.py internals.
It sets up logging handlers, formatters, and log levels based on the configuration provided.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import discord
from rich.logging import RichHandler
from rich.text import Text

from . import CONFIG

__all__ = ["setup_logging"]


class FileFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        formatted_str = super().format(record)
        if record.__dict__.get("markup", False):
            # Remove the "[some markup] text [/some markup]" markup for rich.
            formatted_str = Text.from_markup(formatted_str).plain
        return formatted_str


def setup_logging() -> None:
    """
    Set up logging for the bot and discord.py internals.
    This function configures the logging handlers, formatters, and log levels based on the provided configuration.
    """
    # Configure root logging level.
    project_root_logger = logging.getLogger("modmail")
    project_root_logger.setLevel(CONFIG.logging.root_level)

    # Configure RichHandler for console logging with rich formatting.
    formatter = logging.Formatter(CONFIG.logging.stdout_format)
    handler = RichHandler(
        show_level=True,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        log_time_format=lambda dt: Text(dt.strftime("%X,%f")[:-3]),
        tracebacks_suppress=[discord],
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

    logger_dc3 = logging.getLogger("discord.http")
    logger_dc3.setLevel(CONFIG.logging.discord_http_level)

    logger_dc4 = logging.getLogger("discord.gateway")
    logger_dc4.setLevel(CONFIG.logging.discord_gateway_level)

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
