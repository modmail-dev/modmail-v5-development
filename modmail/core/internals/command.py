"""
modmail.core.internals.command
==============================
This module contains a custom implementation of a lazy hybrid command decorator for Modmail's cogs.
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine, Generic, TypeAlias, TypeVar

import discord
from discord import app_commands
from discord.ext import commands

from ... import CONFIG

__all__ = ["LazyHybridCommand", "LazyHybridGroup", "lazy_hybrid_command", "lazy_hybrid_group", "wrap"]


Co: TypeAlias = Callable[..., Coroutine[Any, Any, Any]]
T = TypeVar("T", bound=Co)  # A 'Co' that takes any parameters and returns any type
U = TypeVar("U", bound=Co)
A = TypeVar("A")
Deco: TypeAlias = Callable[[T], T]  # A decorator that takes a 'Co' and returns a 'Co'
DecoFactory: TypeAlias = Callable[..., Deco[T]]  # A deco factory that takes any arguments and returns a 'Deco'
HcHg: TypeAlias = commands.HybridCommand[Any, Any, Any] | commands.HybridGroup[Any, Any, Any]


class LazyHybridCommand(Generic[T]):
    """
    A class that represents a lazy hybrid command.

    Allows the injection of the cog name into the __qualname__ of the callback function.
    """

    __slots__ = ("base_func", "callback", "args", "kwargs", "wrappers")

    def __init__(self, func: T, args: Any, kwargs: Any):
        self.base_func: Callable[..., Callable[[T], HcHg]] = staticmethod(commands.hybrid_command)
        self.callback = func
        self.args = args
        self.kwargs = kwargs

        # Store the wrappers for the command (discord.py's command decorators)
        if hasattr(func, "__modmail_wrappers__"):
            self.wrappers: list[tuple[DecoFactory[T], tuple[Any, ...], dict[str, Any]]] = (
                func.__modmail_wrappers__
            )  # pyright: ignore [reportFunctionMemberAccess]
        else:
            self.wrappers = []

        # Allow the commands should be used in guilds only
        self.wrappers.append((commands.guild_only, (), {}))

        # Set the default permissions for the slash command
        if CONFIG.permission.slash_minimum_permission_int != 0:
            self.wrappers.append(
                (
                    app_commands.default_permissions,
                    (discord.Permissions(CONFIG.permission.slash_minimum_permission_int),),
                    {},
                )
            )

    @property
    def _callback_name(self) -> str:
        """
        The name of the command.
        """
        return self.callback.__name__

    def get_commands(self, cog_name: str) -> dict[str, HcHg]:
        """
        Create the command with the cog name injected into the __qualname__ of the callback function.

        :param cog_name: The cog's name.
        :return: A mapping of function names to commands.
        """
        # Set the __qualname__ of the function to include the cog name
        if not self.callback.__qualname__.startswith(f"{cog_name}."):
            self.callback.__qualname__ = f"{cog_name}.{self._callback_name}"

        # Apply the wrappers to the function directly (app_command decorators does not work on command)
        func = self.callback
        for wrapper_func, wrapper_args, wrapper_kwargs in self.wrappers:
            func = wrapper_func(*wrapper_args, **wrapper_kwargs)(func)

        # Create the command using the base function (hybrid_command/hybrid_group)
        command = self.base_func(*self.args, **self.kwargs)(func)

        return {self._callback_name: command}


class LazyHybridGroup(LazyHybridCommand[T]):
    """
    A class that represents a lazy hybrid group command.

    Allows the injection of the cog name into the __qualname__ of the callback function.
    """

    __slots__ = ("children",)

    def __init__(self, func: T, args: Any, kwargs: Any):
        super().__init__(func, args, kwargs)
        self.base_func: Callable[..., Callable[[T], HcHg]] = staticmethod(commands.hybrid_group)
        self.children: list[LazyHybridCommand[Any]] = []

    def get_commands(self, cog_name: str) -> dict[str, HcHg]:
        # Get the hybrid group of the func
        command_mapping = super().get_commands(cog_name)
        group = command_mapping[self._callback_name]
        assert isinstance(group, commands.HybridGroup), "Expected a HybridGroup"

        for child in self.children:
            # Change the base_func of the child to the group's
            if isinstance(child, LazyHybridGroup):
                child.base_func = group.group
            elif isinstance(child, LazyHybridCommand):  # pyright: ignore [reportUnnecessaryIsInstance]
                child.base_func = group.command
            else:
                raise TypeError(f"Unexpected child type: {type(child)}")  # pragma: no cover
            # Add the child to the command mapping
            child_command_mapping = child.get_commands(cog_name)
            command_mapping.update(child_command_mapping)
        return command_mapping

    def command(self, *args: Any, **kwargs: Any) -> Callable[[U], LazyHybridCommand[U]]:
        """
        Create a hybrid child command.
        Accepts the same arguments as discord.py's hybrid_command.
        """

        def decorator(func: U) -> LazyHybridCommand[U]:
            child = LazyHybridCommand(func, args, kwargs)
            self.children.append(child)
            return child

        return decorator

    def group(self, *args: Any, **kwargs: Any) -> Callable[[U], LazyHybridGroup[U]]:
        """
        Create a hybrid child group.
        Accepts the same arguments as discord.py's hybrid_group.
        """

        def decorator(func: U) -> LazyHybridGroup[U]:
            child = LazyHybridGroup(func, args, kwargs)
            self.children.append(child)
            return child

        return decorator


def lazy_hybrid_command(*args: Any, **kwargs: Any) -> Callable[[T], LazyHybridCommand[T]]:
    """
    Store the args for hybrid_command, but don't create the actual command yet.
    This is necessary to inject the cog name into __qualname__ of the callback func later.
    Accepts the same arguments as discord.py's hybrid_command.
    """

    def decorator(func: T) -> LazyHybridCommand[T]:
        return LazyHybridCommand(func, args, kwargs)

    return decorator


def lazy_hybrid_group(*args: Any, **kwargs: Any) -> Callable[[T], LazyHybridGroup[T]]:
    """
    Store the args for hybrid_group, but don't create the actual command yet.
    This is necessary to inject the cog name into __qualname__ of the callback func later.
    Accepts the same arguments as discord.py's hybrid_group.
    """

    def decorator(func: T) -> LazyHybridGroup[T]:
        return LazyHybridGroup(func, args, kwargs)

    return decorator


def wrap(dpy_func: Any, *args: Any, **kwargs: Any) -> Callable[[A], A]:
    """
    A decorator that wraps a function with a discord.py command decorator.
    Example: @wrap(commands.has_permissions, manage_messages=True)
    """

    def decorator(func: A) -> A:
        # If the function is already a lazy class
        if isinstance(func, LazyHybridCommand):
            func.wrappers.append((dpy_func, args, kwargs))  # pyright: ignore [reportUnknownMemberType]
        else:
            # Otherwise, add the wrapper to the function directly
            if not hasattr(func, "__modmail_wrappers__"):
                func.__modmail_wrappers__ = []  # pyright: ignore [reportAttributeAccessIssue]
            func.__modmail_wrappers__.append(
                (dpy_func, args, kwargs)
            )  # pyright: ignore [reportAttributeAccessIssue, reportUnknownMemberType]
        return func  # pyright: ignore [reportUnknownVariableType]

    return decorator
