"""Configuration loader for the Modmail bot.

This module provides functionality to load and validate the configuration file for the Modmail bot.
It reads the configuration from a YAML file and parses it into Pydantic models for further use.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pydantic
import yaml

from .models import Config

logger = logging.getLogger(__name__)


__all__ = ["load_config"]


def load_config(file_path: str | Path) -> Config | None:
    """Loads the YAML config from the given file path.

    Args:
        file_path: The path to the YAML config file.

    Returns:
        The parsed Config object if successful, None if the file was not found
        or couldn't be parsed.
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    try:
        with file_path.open("r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.critical("Config file not found at %s.", file_path)
        return None
    except PermissionError:
        logger.critical("No permissions to open the file at %s (or the path is invalid).", file_path)
        return None
    except OSError as e:
        logger.critical("Failed to open the config file: %s.", e, exc_info=True)
        return None

    if not isinstance(config_data, dict):
        logger.critical("Invalid config file at %s.", file_path)
        return None

    try:
        return Config(**config_data)  # pyright: ignore [reportUnknownArgumentType]
    except pydantic.ValidationError as e:
        logger.critical("Invalid config file at %s:\n%s", file_path, e)
        return None
