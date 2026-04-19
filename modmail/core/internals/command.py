"""Custom implementation of lazy hybrid command decorator for Modmail's cogs.

This module provides a lazy loading approach for hybrid commands that allows injecting the cog name
into the __qualname__ of callback functions so discord.py thinks the command belongs to the cog.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from ... import CONFIG
from ...errors import NotInTicketError, StaffGuildNotConfiguredError

if TYPE_CHECKING:
    from .context import Context

__all__ = [
    "LazyHybridCommand",
    "LazyHybridGroup",
    "in_modmail_ticket",
    "lazy_hybrid_command",
    "lazy_hybrid_group",
    "wrap",
]


type Co = Callable[..., Coroutine[Any, Any, Any]]
type DecoFactory[T: Co] = Callable[
    ..., Callable[[T], T]
]  # A deco factory that takes any arguments and returns a decorator
type HcHg = commands.HybridCommand[Any, Any, Any] | commands.HybridGroup[Any, Any, Any]


class LazyHybridCommand[T: Co]:
    """A class representing a lazy hybrid command.

    This allows the injection of the cog name into the __qualname__ of the callback function.
    Commands are created lazily, meaning they are only instantiated when the cog is loaded.

    Attributes:
        base_func: Function used to create the command (commands.hybrid_command).
        callback: The original function that will become the command callback.
        wrappers: List of decorators to apply to the command.
    """

    __slots__ = ("args", "base_func", "callback", "kwargs", "wrappers")

    def __init__(self, func: T, args: Any, kwargs: Any) -> None:
        """Initialize a lazy hybrid command.

        Args:
            func: The function to transform into a command.
            args: Positional arguments for the command constructor.
            kwargs: Keyword arguments for the command constructor.
        """
        self.base_func: Callable[..., Callable[[T], HcHg]] = commands.hybrid_command
        self.callback = func
        self.args = args
        self.kwargs = kwargs

        # Store the wrappers for the command (discord.py's command decorators)
        if hasattr(func, "__modmail_wrappers__"):
            self.wrappers: list[tuple[DecoFactory[T], tuple[Any, ...], dict[str, Any]]] = func.__modmail_wrappers__  # pyright: ignore [reportFunctionMemberAccess]
        else:
            self.wrappers = []

        # Allow the commands should be used in guilds only
        self.wrappers.append((commands.guild_only, (), {}))

        # Set the default permissions for the slash command
        if CONFIG.permission.slash_minimum_permission_int != 0:
            self.wrappers.append((
                app_commands.default_permissions,
                (discord.Permissions(CONFIG.permission.slash_minimum_permission_int),),
                {},
            ))

    @property
    def _callback_name(self) -> str:
        """Get the name of the command.

        Returns:
            The name of the command (function name).
        """
        return self.callback.__name__

    def get_commands(self, cog_name: str) -> dict[str, HcHg]:
        """Create the command with the cog name injected into the callback function.

        This method updates the __qualname__ of the callback function to include the cog name,
        applies all registered wrappers, and creates the actual command object.

        Args:
            cog_name: The name of the containing cog.

        Returns:
            A mapping of function names to command objects.
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


class LazyHybridGroup[T: Co](LazyHybridCommand[T]):
    """A class representing a lazy hybrid group command.

    Extends LazyHybridCommand to provide group command functionality.
    Group commands can have child commands and subgroups.

    Attributes:
        children: List of child commands and subgroups.
        base_func: Function used to create the command (commands.hybrid_group).
        callback: The original function that will become the command callback.
        wrappers: List of decorators to apply to the command.
    """

    __slots__ = ("children",)

    def __init__(self, func: T, args: Any, kwargs: Any) -> None:
        """Initialize a lazy hybrid group.

        Args:
            func: The function to transform into a group command.
            args: Positional arguments for the group command constructor.
            kwargs: Keyword arguments for the group command constructor.
        """
        super().__init__(func, args, kwargs)
        self.base_func: Callable[..., Callable[[T], HcHg]] = commands.hybrid_group
        self.children: list[LazyHybridCommand[Any]] = []

    def get_commands(self, cog_name: str) -> dict[str, HcHg]:
        """Create the group command and all its children.

        Args:
            cog_name: The name of the containing cog.

        Returns:
            A mapping of function names to command objects.

        Raises:
            TypeError: If a child is not a LazyHybridGroup or LazyHybridCommand.
        """
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

    def command[U: Co](self, *args: Any, **kwargs: Any) -> Callable[[U], LazyHybridCommand[U]]:
        """Create a hybrid child command for this group.

        Args:
            *args: Positional arguments to pass to the command constructor.
            **kwargs: Keyword arguments to pass to the command constructor.

        Returns:
            A decorator that transforms a function into a child command.
        """

        def decorator(func: U) -> LazyHybridCommand[U]:
            child = LazyHybridCommand(func, args, kwargs)
            self.children.append(child)
            return child

        return decorator

    def group[U: Co](self, *args: Any, **kwargs: Any) -> Callable[[U], LazyHybridGroup[U]]:
        """Create a hybrid child group for this group.

        Args:
            *args: Positional arguments to pass to the group constructor.
            **kwargs: Keyword arguments to pass to the group constructor.

        Returns:
            A decorator that transforms a function into a child group.
        """

        def decorator(func: U) -> LazyHybridGroup[U]:
            child = LazyHybridGroup(func, args, kwargs)
            self.children.append(child)
            return child

        return decorator


def lazy_hybrid_command[T: Co](*args: Any, **kwargs: Any) -> Callable[[T], LazyHybridCommand[T]]:
    """Create a lazy hybrid command decorator.

    This stores the arguments for hybrid_command but doesn't create the actual command yet,
    allowing for cog name injection later.

    Args:
        *args: Positional arguments to pass to commands.hybrid_command.
        **kwargs: Keyword arguments to pass to commands.hybrid_command.

    Returns:
        A decorator that transforms a function into a lazy hybrid command.
    """

    def decorator(func: T) -> LazyHybridCommand[T]:
        return LazyHybridCommand(func, args, kwargs)

    return decorator


def lazy_hybrid_group[T: Co](*args: Any, **kwargs: Any) -> Callable[[T], LazyHybridGroup[T]]:
    """Create a lazy hybrid group decorator.

    This stores the arguments for hybrid_group but doesn't create the actual group yet,
    allowing for cog name injection later.

    Args:
        *args: Positional arguments to pass to commands.hybrid_group.
        **kwargs: Keyword arguments to pass to commands.hybrid_group.

    Returns:
        A decorator that transforms a function into a lazy hybrid group.
    """

    def decorator(func: T) -> LazyHybridGroup[T]:
        return LazyHybridGroup(func, args, kwargs)

    return decorator


def wrap[T](dpy_func: Any, *args: Any, **kwargs: Any) -> Callable[[T], T]:
    """Wrap a function with a discord.py command decorator.

    This allows applying discord.py decorators to lazy hybrid commands.

    Args:
        dpy_func: The discord.py decorator function to apply.
        *args: Positional arguments to pass to the decorator.
        **kwargs: Keyword arguments to pass to the decorator.

    Returns:
        A decorator that applies the discord.py decorator to a function.

    Example:
        @wrap(commands.has_permissions, manage_messages=True)
        @lazy_hybrid_command()
        async def example(ctx):
            ...
    """

    def decorator(func: T) -> T:
        # If the function is already a lazy class
        if isinstance(func, LazyHybridCommand):
            func.wrappers.append((dpy_func, args, kwargs))  # pyright: ignore [reportUnknownMemberType]
        else:
            # Otherwise, add the wrapper to the function directly
            if not hasattr(func, "__modmail_wrappers__"):
                func.__modmail_wrappers__ = []  # pyright: ignore [reportAttributeAccessIssue]
            func.__modmail_wrappers__.append((dpy_func, args, kwargs))  # pyright: ignore [reportAttributeAccessIssue, reportUnknownMemberType]
        return func  # pyright: ignore [reportUnknownVariableType]

    return decorator


def in_modmail_ticket() -> Any:
    """Check if the command is being invoked in a Modmail ticket.

    This decorator also applies the guild_only decorator to ensure the command is only
    available in servers.

    Returns:
        A check function that returns True if the command is in a Modmail ticket.
    """

    async def predicate(ctx: Context) -> bool:
        """Check if the command is being invoked in a Modmail ticket.

        Args:
            ctx: The command context.

        Returns:
            True if the command is in a Modmail ticket, False otherwise.

        Raises:
            NotInTicketError: If the command is not in a Modmail ticket.
            StaffGuildNotConfiguredError: If Modmail is not configured.
        """
        if not ctx.bot.staff_guild.is_configured():
            raise StaffGuildNotConfiguredError("Modmail is not configured.")

        if ctx.guild is None or ctx.guild.id != ctx.bot.staff_guild.guild_id:
            raise NotInTicketError("This command can only be used in Modmail tickets.")

        ticket_model = await ctx.bot.database_client.get_ticket_by_channel(ctx.channel.id, only_open=True)
        if ticket_model is None:
            raise NotInTicketError("This command can only be used in Modmail tickets.")
        return True

    return wrap(commands.guild_only)(wrap(lambda: commands.check(predicate)))
