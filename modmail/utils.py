"""
modmail.util
============
This module contains utility functions that provide common, reusable functionality
for the project. These functions are designed to be used across different parts
of the codebase to avoid redundancy and promote code reuse.
"""

from __future__ import annotations

import logging
from typing import Any

from discord.ext import commands

__all__ = ["strtobool", "int_to_colour_hex", "colour_hex_to_int", "sanitize_user_command_name", "get_command_name"]

logger = logging.getLogger(__name__)


def strtobool(val: str) -> int:
    """Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.

    This is a copy of the `distutils.util.strtobool` function.
    """
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return 1
    elif val in ("n", "no", "f", "false", "off", "0"):
        return 0
    else:
        raise ValueError(f"invalid truth value {val!r}")


def int_to_colour_hex(value: int) -> str:
    """Convert an integer to a hex color string.

    :param value: The integer value to convert.
    :return: A hex color string in the format '#RRGGBB'.
    """
    return f"#{value:06X}"


def colour_hex_to_int(value: str) -> int:
    """Convert a hex color string to an integer.

    :param value: The hex color string in the format '#RRGGBB'.
    :return: The integer value of the color.
    """
    return int(value.lstrip("#"), 16)


def sanitize_user_command_name(command_name: str) -> str:
    """
    Sanitize a user-provided command name.

    :param command_name: The command name to sanitize.
    :return: The sanitized command name.
    """
    # "_" -> " ", "*" -> "+", casefold, strip
    command_name = command_name.casefold().strip().replace("_", " ").replace("*", "+")
    command_name_no_wildcard = command_name.split("+")[0].strip()
    if "+" in command_name:
        command_name = command_name_no_wildcard + "+"
    return command_name


def get_command_name(command: commands.Command[Any, Any, Any]) -> str:
    """
    Get the command name from a command.

    :param command: The discord.py command.
    :return: The command name.
    """
    # Check if the command has an override set in the config.
    command_name = command.callback.__name__.casefold()
    if command_name.endswith("_command"):
        command_name = command_name[:-8]
        command_name = command_name.replace("_", " ").strip()
    else:
        # TODO: move this warning to when a new command is registered/created
        logger.debug(
            "Command name does not end with _command: %s (%s)",
            command.qualified_name,
            command.callback.__name__,
        )
        command_name = command.qualified_name  # Use the full qualified name as the command name
    return command_name
