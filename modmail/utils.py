"""Shared utility functions used across the project."""

from __future__ import annotations

import weakref
from functools import partial
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "MultiKeyCollection",
    "color_hex_to_int",
    "int_to_color_hex",
    "is_bot",
    "strtobool",
]


def strtobool(val: str) -> bool:
    """Convert a string representation of truth to True or False.

    Args:
        val: The string value to convert.

    Returns:
        True for true values, False for false values.

    Raises:
        ValueError: If the input string is not a recognized truth value.

    Note:
        True values are `y`, `yes`, `t`, `true`, `on`, and `1`.
        False values are `n`, `no`, `f`, `false`, `off`, and `0`.
    """
    val = val.casefold()
    if val in {"y", "yes", "t", "true", "on", "1"}:
        return True
    if val in {"n", "no", "f", "false", "off", "0"}:
        return False
    raise ValueError(f"invalid truth value {val!r}")


def int_to_color_hex(value: int) -> str:
    """Convert a 24-bit integer to a `#RRGGBB` hex color string.

    32-bit values are treated as RGBA (`0xRRGGBBAA`); the low alpha byte is discarded.

    Args:
        value: RGB (`0xRRGGBB`) color integer.

    Returns:
        Hex color string in `#RRGGBB` format, or `#000000` if the value is out of range.
    """
    if not 0 <= value <= 0xFFFFFFFF:  # noqa: PLR2004
        return "#000000"
    return f"#{(value >> 8) & 0xFFFFFF:06X}" if value > 0xFFFFFF else f"#{value:06X}"  # noqa: PLR2004


def color_hex_to_int(value: str) -> int:
    """Convert a hex color string to a 24-bit RGB integer.

    Accepts 3-digit shorthand (`RGB` → `RRGGBB`), 6-digit RGB (`RRGGBB`), and
    8-digit RGBA (`RRGGBBAA`) — all with or without a leading `#`.
    8-digit values have the trailing alpha byte discarded.

    Args:
        value: Hex color string in `#RGB`, `#RRGGBB`, or `#RRGGBBAA` format.

    Returns:
        24-bit RGB integer, or `0x000000` if the input is not valid hex or exceeds 32 bits.
    """
    stripped = value.lstrip("#")
    if len(stripped) == 3:  # noqa: PLR2004
        stripped = "".join(c * 2 for c in stripped)
    try:
        n = int(stripped, 16)
    except ValueError:
        return 0x000000
    if n > 0xFFFFFFFF:  # noqa: PLR2004
        return 0x000000
    return (n >> 8) & 0xFFFFFF if n > 0xFFFFFF else n  # noqa: PLR2004


def is_bot(user_or_role: discord.Member | discord.User | discord.Role) -> bool:
    """Check if a user or role is a bot.

    Args:
        user_or_role: The member, user, or role to check.

    Returns:
        `True` if `user_or_role` is a bot user or a bot-managed role.
    """
    if isinstance(user_or_role, discord.Member | discord.User):
        return user_or_role.bot
    return user_or_role.tags is not None and user_or_role.tags.is_bot_managed()


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
        """Get an object by any of its keys.

        Args:
            key_value: The key, value pair to search for.

        Returns:
            The object if found, otherwise None.

        Raises:
            KeyError: If the key is not found or if key and value pair is not found.
        """
        key, value = key_value
        if key not in self.key_names:
            raise KeyError(f"Key '{key}' is not found")

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
        """Remove a dead weakref from the index when its object is garbage collected.

        Args:
            ref: Dead weak reference (unused).
            key: Index key the entry lives under.
            value: Index value identifying the entry to remove.
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
