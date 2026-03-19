"""Modmail initialization module.

This module initializes the bot by loading the configuration and setting up the
necessary environment. It handles platform-specific configurations and ensures
that logging is properly configured.
"""

from __future__ import annotations

import datetime
import logging as _logging
import sys
from importlib.metadata import version
from textwrap import dedent
from typing import NoReturn

from .config import Config, load_config

__all__ = ["__version__", "init", "run_bot"]

__version__ = version("modmail.py")

logger = _logging.getLogger(__name__)


# Global variable to store the loaded configuration.
CONFIG: Config


def init(config_file_path: str = "config.yaml", *, configure_logging: bool = True) -> None:
    """Initialize the bot by loading the configuration.

    Args:
        config_file_path: Path to the configuration file. Defaults to "config.yaml".
        configure_logging: Whether to configure logging when logging is enabled in the configs.
    """
    global CONFIG  # noqa: PLW0603
    # noinspection PyPep8Naming
    CONFIG_ = load_config(config_file_path)  # noqa: N806
    if CONFIG_ is None:
        logger.critical("Failed to load config. Exiting.")
        sys.exit(1)
    CONFIG = CONFIG_  # pyright: ignore [reportConstantRedefinition]

    if configure_logging and CONFIG.logging.enabled:
        from .logging import setup_logging

        setup_logging()

    logger.debug("Loaded config: %s", CONFIG.model_dump_json())


def run_bot() -> NoReturn:
    """Run the Modmail bot.

    This function initializes the Bot class and starts its operation.
    It handles the event loop and database connection, displaying
    startup information including bot version and configuration details.

    This function does not return as it runs the bot until termination.
    """
    if "CONFIG" not in globals():
        logger.warning("init() was not called. Calling init() with the default args.")
        init()

    modmail_ascii_art = dedent(
        r"""
        ___  ___          _                 _ _
        |  \/  |         | |               (_) |
        | .  . | ___   __| |_ __ ___   __ _ _| |
        | |\/| |/ _ \ / _` | '_ ` _ \ / _` | | |
        | |  | | (_) | (_| | | | | | | (_| | | |
        \_|  |_/\___/ \__,_|_| |_| |_|\__,_|_|_|
        """
    )
    current_time_text = datetime.datetime.now(tz=datetime.UTC).astimezone().strftime("%B %d, %Y %H:%M:%S %Z")
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    allowed_locale = CONFIG.allowed_locales
    enabled_locales = ", ".join(
        [CONFIG.default_locale] + [locale for locale in allowed_locale if locale != CONFIG.default_locale]
    )

    modmail_text_lines: list[str] = []
    modmail_text_lines += modmail_ascii_art.split("\n")
    modmail_text_lines += ["https://github.com/modmail-dev/modmail"]
    modmail_text_lines += [""]
    modmail_text_lines += [f"Starting at {current_time_text}"]
    modmail_text_lines += [
        (
            f"Version: {__version__} | Python: {python_version} | "
            f"Language{'s' if len(CONFIG.allowed_locales) != 1 else ''}: {enabled_locales}"
        )
    ]
    modmail_text_lines += [""]
    modmail_text_width = len(max(modmail_text_lines, key=len)) + 10

    logger.info(
        "[bold bright_magenta] %s",
        "\n".join([line.center(modmail_text_width) for line in modmail_text_lines]),
        extra={"markup": True, "highlighter": None},
    )

    from .core import Bot

    bot = Bot()
    bot.run_bot()
