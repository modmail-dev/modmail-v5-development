"""
modmail.core.commands.command
=============================
This module contains a custom implementation of a lazy hybrid command decorator for Modmail's cogs.
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from discord.ext import commands

__all__ = ["LazyHybridCommand", "lazy_hybrid_command"]


class LazyHybridCommand:
    """
    A class that represents a lazy hybrid command.

    Allows the injection of the cog name into the __qualname__ of the callback function.
    """

    __slot__ = ("func", "name", "args", "kwargs")

    def __init__(self, func: Callable[..., Coroutine[Any, Any, Any]], args: Any, kwargs: Any):
        self.func = func
        self.name: str = func.__name__
        self.args = args
        self.kwargs = kwargs

    def get_command(self, cog_name: str) -> commands.HybridCommand[Any, Any, Any]:
        """
        Create the command with the cog name injected into the __qualname__ of the callback function.

        :param cog_name: The cog's name.
        :return: The hybrid command.
        """
        if not self.func.__qualname__.startswith(f"{cog_name}."):
            self.func.__qualname__ = f"{cog_name}.{self.func.__name__}"
        return commands.hybrid_command(*self.args, **self.kwargs)(self.func)


def lazy_hybrid_command(
    *args: Any, **kwargs: Any
) -> Callable[[Callable[..., Coroutine[Any, Any, Any]]], LazyHybridCommand]:
    """
    Store the args for hybrid_command, but don't create the actual command yet.
    This is necessary to inject the cog name into __qualname__ of the callback func later.
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> LazyHybridCommand:
        return LazyHybridCommand(func, args, kwargs)

    return decorator
