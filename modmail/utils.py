"""Utility functions module.

This module contains utility functions that provide common, reusable functionality
for the project. These functions are designed to be used across different parts
of the codebase to avoid redundancy and promote code reuse.
"""

from __future__ import annotations

import logging
from typing import Any

from discord.ext import commands

__all__ = ["colour_hex_to_int", "get_command_name", "int_to_colour_hex", "sanitize_user_command_name", "strtobool"]

logger = logging.getLogger(__name__)


def strtobool(val: str) -> bool:
    """Convert a string representation of truth to True or False.

    Args:
        val: The string value to convert.

    Returns:
        True for true values, False for false values.

    Raises:
        ValueError: If the input string is not a recognized truth value.

    Note:
        True values are 'y', 'yes', 't', 'true', 'on', and '1'.
        False values are 'n', 'no', 'f', 'false', 'off', and '0'.
    """
    val = val.casefold()
    if val in {"y", "yes", "t", "true", "on", "1"}:
        return True
    if val in {"n", "no", "f", "false", "off", "0"}:
        return False
    raise ValueError(f"invalid truth value {val!r}")


def int_to_colour_hex(value: int) -> str:
    """Convert an integer to a hex color string.

    Args:
        value: The hex-integer value to convert.

    Returns:
        A hex color string in the format '#RRGGBB'.
    """
    return f"#{value:06X}"


def colour_hex_to_int(value: str) -> int:
    """Convert a hex color string to an integer.

    Args:
        value: The hex color string in the format '#RRGGBB' or 'RRGGBB'.

    Returns:
        The hex-integer value of the color.
    """
    return int(value.lstrip("#"), 16)


def sanitize_user_command_name(command_name: str) -> str:
    """Sanitize a user-provided command name.

    Performs the following operations:
    - Converts to lowercase.
    - Strips whitespace.
    - Replaces underscores with spaces.
    - Replaces asterisks with plus signs.
    - Ensures wildcards are properly formatted.

    Args:
        command_name: The command name to sanitize.

    Returns:
        The sanitized command name.
    """
    # "_" -> " ", "*" -> "+", casefold, strip
    command_name = command_name.casefold().strip().replace("_", " ").replace("*", "+")
    command_name_no_wildcard = command_name.split("+")[0].strip()
    if "+" in command_name:
        command_name = command_name_no_wildcard + "+"
    return command_name


def get_command_name(command: commands.Command[Any, Any, Any]) -> str:
    """Get the command name from a command object.

    Extracts the command name from the callback function name,
    removing "_command" suffix and replacing underscores with spaces.

    Args:
        command: The discord.py command object.

    Returns:
        The formatted command name.
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
