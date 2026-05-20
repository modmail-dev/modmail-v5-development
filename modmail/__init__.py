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
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from .config import Config

    CONFIG: Config

__all__ = ["CONFIG", "__version__", "init", "run_bot"]

__version__ = version("modmail.py")

logger = _logging.getLogger(__name__)

_state: dict[str, Config] = {}


def __getattr__(name: str) -> object:
    if name == "CONFIG":
        try:
            return _state["config"]
        except KeyError:
            raise RuntimeError("modmail.CONFIG is not available — call modmail.init() first") from None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def init(config_file_path: str = "config.yaml", *, configure_logging: bool = True) -> None:
    """Initialize the bot by loading the configuration.

    Args:
        config_file_path: Path to the configuration file. Defaults to "config.yaml".
        configure_logging: Whether to configure logging when logging is enabled in the configs.
    """
    from .config import load_config

    config = load_config(config_file_path)
    if config is None:
        logger.critical("Failed to load config. Exiting.")
        sys.exit(1)
    _state["config"] = config

    if configure_logging and config.logging.enabled:
        from .logging import setup_logging

        setup_logging()

    logger.debug("Loaded config: %s", config.model_dump_json(indent=2))


def run_bot() -> NoReturn:
    """Run the Modmail bot.

    This function initializes the Bot class and starts its operation.
    It handles the event loop and database connection, displaying
    startup information including bot version and configuration details.

    This function does not return as it runs the bot until termination.
    """
    if "config" not in _state:
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
    config = _state["config"]
    locale_names = [config.default_locale]
    locale_names += [loc for loc in config.allowed_locales if loc != config.default_locale]
    enabled_locales = ", ".join(locale_names)

    modmail_text_lines: list[str] = []
    modmail_text_lines += modmail_ascii_art.split("\n")
    modmail_text_lines += ["https://github.com/modmail-dev/modmail"]
    modmail_text_lines += [""]
    modmail_text_lines += [f"Starting at {current_time_text}"]
    modmail_text_lines += [
        (
            f"Version: {__version__} | Python: {python_version} | "
            f"Language{'s' if len(config.allowed_locales) != 1 else ''}: {enabled_locales}"
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
