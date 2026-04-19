"""A subclass of discord.py's command.ext.Cog with extended functionality.

This module provides a custom Cog implementation that extends Discord.py's
standard Cog with additional features such as localization, embedded messages,
and improved context handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord.ext import commands

if TYPE_CHECKING:
    from collections.abc import Callable

    from .. import Bot
    from .command import LazyHybridCommand

__all__ = [
    "Cog",
    "create_cog",
]


class Cog(commands.Cog, group_auto_locale_strings=False):
    """A custom Cog class that extends the functionality of discord.py's Cog."""

    def __init__(self, bot: Bot) -> None:
        """Initialize a custom Cog with extended functionality.

        Args:
            bot: The bot instance this cog will be attached to.
        """
        self.bot = bot

    # TODO: Add a before invoke hook (here or in bot) that checks if using ctx.send()
    # and warns to use cog.send().


def create_cog(
    name: str,
    *,
    all_commands: list[LazyHybridCommand[Any]] | None = None,
    other_methods: list[Callable[..., Any]] | None = None,
) -> type[Cog]:
    """Create a new Cog class dynamically at runtime.

    This function allows for programmatic creation of Cogs, which can be useful
    for modular bot design patterns.

    Args:
        name: The name to give the created cog.
        all_commands: A list of LazyHybridCommand objects to add to the cog.
        other_methods: A list of callable methods to add to the cog.

    Returns:
        A new Cog subclass with the specified name and commands.
    """
    methods: dict[
        str,
        commands.HybridCommand[Any, Any, Any] | commands.HybridGroup[Any, Any, Any] | Callable[..., Any],
    ] = {}

    if all_commands:
        for command in all_commands:
            methods.update(command.get_commands(name))

    if other_methods:
        for method in other_methods:
            methods[method.__name__] = method

    # noinspection PyTypeChecker
    return type(name, (Cog,), methods, group_auto_locale_strings=False)
