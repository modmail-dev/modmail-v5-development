"""
modmail
=======
This module initializes the bot by loading the configuration and setting up the necessary environment.
It handles platform-specific configurations and ensures that logging is properly configured.
"""

from __future__ import annotations

__version__ = "5.0a1"

import datetime
import logging as _logging
import sys
from textwrap import dedent
from typing import TYPE_CHECKING, NoReturn

from .config import load_config

if TYPE_CHECKING:
    from .config.models.config_model import Config

__all__ = ["init", "run_bot"]

logger = _logging.getLogger(__name__)


if sys.platform == "win32":
    import asyncio

    try:
        # This is a Windows-specific event loop policy that allows for better performance on Windows.
        # Should already been default in Python 3.8+.
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        import warnings

        warnings.warn("Failed to use WindowsProactorEventLoopPolicy.", RuntimeWarning)


# Global variable to store the loaded configuration.
CONFIG: Config


def init(config_file_path: str = "config.yaml") -> None:
    """
    Initialize the bot by loading the configuration from the specified file path.

    :param config_file_path: Path to the configuration file.
    """
    global CONFIG
    _CONFIG = load_config(config_file_path)
    if _CONFIG is None:
        logger.critical("Failed to load config. Exiting.")
        sys.exit(1)
    CONFIG = _CONFIG  # type: ignore[reportConstantRedefinition]

    if CONFIG.logging.enabled:
        from .logging import setup_logging

        setup_logging()


def run_bot() -> NoReturn:
    """
    Run the bot.
    This function is a wrapper around the Bot class's run method.
    It handles the event loop and database connection.
    """
    if "CONFIG" not in globals():
        logger.warning("init() was not called. Calling init() with the default args.")
        init()

    modmail_text_lines: list[str] = []
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
    current_time_text = (
        datetime.datetime.now(tz=datetime.timezone.utc).astimezone().strftime("%B %d, %Y %H:%M:%S %Z")
    )
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    modmail_text_lines += [line for line in modmail_ascii_art.split("\n")]
    modmail_text_lines += ["https://github.com/modmail-dev/modmail"]
    modmail_text_lines += [""]
    modmail_text_lines += [f"Starting at {current_time_text}"]
    modmail_text_lines += [f"Version: {__version__} | Python: {python_version}"]
    modmail_text_lines += [""]
    modmail_text_width = len(max(modmail_text_lines, key=len)) + 10

    logger.info(
        "[bold bright_magenta]" + "\n".join([line.center(modmail_text_width) for line in modmail_text_lines]),
        extra={"markup": True, "highlighter": None},
    )

    from .core import Bot

    bot = Bot()
    bot.run_bot()


if __name__ == "__main__":
    init()  # TODO: get file path from argv
    run_bot()
