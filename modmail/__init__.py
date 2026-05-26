"""Modmail initialization module."""

from __future__ import annotations

import datetime
import logging as _logging
import sys
from importlib.metadata import version
from pathlib import Path
from textwrap import dedent
from typing import NoReturn

from .config import ConfigStore, config as _config, set_store
from .core import Bot

__all__ = ["Bot", "__version__", "run_bot"]

__version__ = version("modmail.py")

_logger = _logging.getLogger(__name__)


def run_bot(config_file_path: str) -> NoReturn:
    """Run the Modmail bot.

    Args:
        config_file_path: Path to the configuration file.
    """
    try:
        store = ConfigStore(Path(config_file_path))
        set_store(store)
    except Exception:
        _logger.critical("Failed to load config. Exiting.", exc_info=True)
        sys.exit(1)

    _logger.debug("Loaded config: %s", _config.model_dump_json(indent=2))

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
    locale_names = [_config.default_locale]
    locale_names += [loc for loc in _config.allowed_locales if loc != _config.default_locale]
    enabled_locales = ", ".join(locale_names)

    modmail_text_lines: list[str] = []
    modmail_text_lines += modmail_ascii_art.split("\n")
    modmail_text_lines += ["https://github.com/modmail-dev/modmail"]
    modmail_text_lines += [""]
    modmail_text_lines += [f"Starting at {current_time_text}"]
    modmail_text_lines += [
        (
            f"Version: {__version__} | Python: {python_version} | "
            f"Language{'s' if len(_config.allowed_locales) != 1 else ''}: {enabled_locales}"
        )
    ]
    modmail_text_lines += [""]
    modmail_text_width = len(max(modmail_text_lines, key=len)) + 10

    _logger.info(
        "[bold bright_magenta] %s",
        "\n".join([line.center(modmail_text_width) for line in modmail_text_lines]),
        extra={"markup": True, "highlighter": None},
    )

    bot = Bot()
    bot.run_bot()
