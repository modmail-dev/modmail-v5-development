"""Utility functions module.

This module contains utility functions that provide common, reusable functionality
for the project. These functions are designed to be used across different parts
of the codebase to avoid redundancy and promote code reuse.
"""

from __future__ import annotations

import logging
import weakref
from collections.abc import Iterator
from functools import partial
from typing import Any

from discord.ext import commands

__all__ = [
    "MultiKeyCollection",
    "colour_hex_to_int",
    "get_command_name",
    "int_to_colour_hex",
    "sanitize_user_command_name",
    "strtobool",
]

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


class MultiKeyCollection[T]:
    """Collection that can access values with different keys.

    This class acts like a multi-key dictionary.
    The object cannot be built-in immutable types like int, str, tuple, etc.

    Examples:
        >>> collection = MultiKeyCollection("key1", "key2")
        >>> collection.add(obj, key1="value1", key2="value2")
        >>> obj = collection["key1", "value1"]
        >>> obj is collection["key2", "value2"]
        >>> collection.remove("key2", "value2")
        >>> collection.get("key1", "value1") is None
    """

    def __init__(self, *key_names: str) -> None:
        """Initialize the MultiKeyCollection.

        Args:
            *key_names: Keys for the collection.

        Raises:
            ValueError: If no key names are provided.
        """
        if len(key_names) < 1:
            raise ValueError("At least one key name is required")

        # value[0] -> object
        self.primary_index: dict[Any, T] = {}

        # key[1:] -> value[1:] -> weakref
        self.other_indices: dict[str, dict[Any, weakref.ReferenceType[T]]] = {key: {} for key in key_names[1:]}
        self.key_names = key_names

    def __len__(self) -> int:
        """Get the number of objects in the collection.

        Returns:
            The number of objects in the collection.
        """
        return len(self.primary_index)

    def __iter__(self) -> Iterator[T]:
        """Iterate over the objects in the collection.

        Returns:
            An iterator over the objects in the collection.
        """
        return iter(self.primary_index.values())

    def __str__(self) -> str:
        """Get a string representation of the collection.

        Returns:
            A string representation of the collection.
        """
        return f"{self.__class__.__name__}({self.key_names}){self.primary_index}"

    def __getitem__(self, key_value: tuple[str, Any]) -> T | None:
        """Get an object by any of its key.

        Args:
            key_value: The key, value pair to search for.

        Returns:
            The object if found, otherwise None.

        Raises:
            ValueError: If the key is not found.
            KeyError: If the key and value pair is not found.
        """
        key, value = key_value
        if key not in self.key_names:
            raise ValueError(f"Attribute '{key}' is not found")

        if key == self.key_names[0]:
            obj = self.primary_index.get(value)
            if obj is not None:
                return obj
            raise KeyError(f"Key '{key}' with value '{value}' not found")

        ref = self.other_indices[key].get(value)
        if ref is not None and (obj := ref()) is not None:
            return obj
        raise KeyError(f"Key '{key}' with value '{value}' not found")

    def get(self, *, default: Any | None = None, **key_mapping: Any) -> T | None:
        """Get an object by its key and value.

        Args:
            default: The default value to return if not found.
            **key_mapping: A single key-value pair to search for.

        Examples:
            >>> collection.get(key1="value1")
            >>> collection.get(key2="value2", default=default_value)

        Returns:
            The object if found, otherwise the default value.

        Raises:
            ValueError: If the key is not found.
        """
        if len(key_mapping) != 1:
            raise ValueError("Key mapping must contain exactly one key-value pair")
        key, value = next(iter(key_mapping.items()))

        if key not in self.key_names:
            raise ValueError(f"Attribute '{key}' is not found")

        if key == self.key_names[0]:
            obj = self.primary_index.get(value)
            return obj if obj is not None else default

        ref = self.other_indices[key].get(value)
        if ref is not None and (obj := ref()) is not None:
            return obj
        return default

    def get_any(self, **key_mapping: Any) -> T | None:
        """Get an object by any of its keys.

        Args:
            **key_mapping: A mapping of keys to values to search for.

        Returns:
            The object if found, otherwise None.

        Raises:
            ValueError: If the key is not found.
        """
        for key, value in key_mapping.items():
            if key not in self.key_names:
                raise ValueError(f"Attribute '{key}' is not found")
            if key == self.key_names[0]:
                obj = self.primary_index.get(value)
                if obj is not None:
                    return obj
            else:
                ref = self.other_indices[key].get(value)
                if ref is not None and (obj := ref()) is not None:
                    return obj
        return None

    def add(self, obj: T, **key_mapping: Any) -> None:
        """Add an object to the collection.

        Args:
            obj: The object to add to the collection.
            **key_mapping: A mapping of keys to values for the object.

        Raises:
            ValueError: If the object is None or already exists in the collection
                        or if the key mapping doesn't contain the correct keys.
        """
        if obj is None:
            raise ValueError("Cannot add None to the collection")

        if set(self.key_names) != set(key_mapping.keys()):
            raise ValueError(
                f"Key mapping must contain keys: {list(self.key_names)} but got {list(key_mapping.keys())}"
            )

        # Check if the object already exists in the collection
        for key, value in key_mapping.items():
            if key == self.key_names[0]:
                if value in self.primary_index:
                    raise ValueError(f"Object with duplicate '{key}' value found: {value}")
            else:
                # Check if the weakref is still alive
                if value in self.other_indices[key]:
                    existing = self.other_indices[key][value]()
                    if existing is not None:  # Check if the reference is still alive
                        raise ValueError(f"Object with duplicate '{key}' value found: {value}")
                    # If reference is dead, it will be replaced

        # Add to collection and indices
        for key, value in key_mapping.items():
            if key == self.key_names[0]:
                self.primary_index[value] = obj
            else:
                self.other_indices[key][value] = weakref.ref(obj, partial(self._cleanup_ref, key=key, value=value))

    def _cleanup_ref(self, ref: weakref.ReferenceType[T], key: str, value: Any) -> None:
        """Remove weakref from index when object is garbage collected.

        Args:
            ref: The weak reference to the object.
            key: The key in the index.
            value: The value in the index.
        """
        if key in self.other_indices and value in self.other_indices[key]:
            del self.other_indices[key][value]

    def remove(self, key: str, value: Any) -> T:
        """Remove an object by a key-value pair from the collection and all indices.

        This is an expensive operation.

        Args:
            key: The key to search for.
            value: The value to search for.

        Returns:
            The object that was removed.

        Raises:
            ValueError: If the key is not found.
            KeyError: If the key and value pair is not found.
        """
        if key not in self.key_names:
            raise ValueError(f"Attribute '{key}' is not found")

        if key == self.key_names[0]:
            obj = self.primary_index.pop(value, None)
            if obj is None:
                raise KeyError(f"Key '{key}' with value '{value}' not found")
        else:
            ref = self.other_indices[key].pop(value, None)
            if ref is None or (obj := ref()) is None:
                raise KeyError(f"Key '{key}' with value '{value}' not found")

        # Remove from all other indices
        for k in self.key_names:
            if k == key:
                continue
            if k == self.key_names[0]:
                for i, j in list(self.primary_index.items()):
                    if j is obj:
                        self.primary_index.pop(i, None)
                        break
            else:
                for i, j in list(self.other_indices[k].items()):
                    if j() is obj:
                        self.other_indices[k].pop(i, None)
                        break
        return obj
