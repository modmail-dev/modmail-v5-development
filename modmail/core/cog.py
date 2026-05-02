"""[`Cog`][] base class, [`create_cog`][] factory, and lazy hybrid command machinery."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, ClassVar

import discord
from discord import app_commands
from discord.ext import commands

from .. import CONFIG
from ..errors import NotInTicketError, StaffGuildNotConfiguredError

if TYPE_CHECKING:
    from .bot import Bot
    from .context import Context

__all__ = [
    "Cog",
    "LazyHybridCommand",
    "LazyHybridGroup",
    "create_cog",
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
    """Deferred wrapper around a hybrid command callback.

    Stores the callback and its decorators without creating a command object, so the cog
    name can be injected into `__qualname__` at load time via [`get_commands`][].

    Attributes:
        base_func: Constructor used to build the command; defaults to `commands.hybrid_command`,
            overridden to the parent group's `.command` or `.group` method by
            [`LazyHybridGroup.get_commands`][].
        callback: The original async function passed to the decorator.
        args: Positional arguments forwarded to the command constructor.
        kwargs: Keyword arguments forwarded to the command constructor.
        wrappers: Deferred decorators (e.g. `app_commands.describe`) applied inside
            [`get_commands`][].
    """

    __slots__ = ("args", "base_func", "callback", "kwargs", "wrappers")

    def __init__(self, func: T, args: Any, kwargs: Any) -> None:
        """Store the callback and its constructor arguments for deferred command creation.

        Args:
            func: The async function that becomes the command callback.
            args: Positional arguments forwarded to `commands.hybrid_command`.
            kwargs: Keyword arguments forwarded to `commands.hybrid_command`.
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
        """The callback's function name, used as the command name."""
        return self.callback.__name__

    def get_commands(self, cog_name: str) -> dict[str, HcHg]:
        """Inject `cog_name` into `__qualname__`, apply wrappers, and return the command dict.

        Args:
            cog_name: Name of the cog that will own this command.

        Returns:
            Mapping of callback name to the constructed [`commands.HybridCommand`][].
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
    """[`LazyHybridCommand`][] that owns child commands and subgroups."""

    __slots__ = ("children",)

    def __init__(self, func: T, args: Any, kwargs: Any) -> None:
        """Store the callback and constructor arguments; initialize `children` to empty.

        Args:
            func: The async function that becomes the group callback.
            args: Positional arguments forwarded to `commands.hybrid_group`.
            kwargs: Keyword arguments forwarded to `commands.hybrid_group`.
        """
        super().__init__(func, args, kwargs)
        self.base_func: Callable[..., Callable[[T], HcHg]] = commands.hybrid_group
        self.children: list[LazyHybridCommand[Any]] = []
        """Child commands and subgroups registered under this group."""

    def get_commands(self, cog_name: str) -> dict[str, HcHg]:
        """Build this group then recursively build all children.

        Args:
            cog_name: Name of the cog that will own this group.

        Returns:
            Mapping of callback name to command object for this group and all descendants.

        Raises:
            TypeError: If a child is not a [`LazyHybridCommand`][] or [`LazyHybridGroup`][].
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
        """Decorator to add a child command to this group.

        Returns:
            A decorator that wraps the function in a [`LazyHybridCommand`][] and registers it.
        """

        def decorator(func: U) -> LazyHybridCommand[U]:
            child = LazyHybridCommand(func, args, kwargs)
            self.children.append(child)
            return child

        return decorator

    def group[U: Co](self, *args: Any, **kwargs: Any) -> Callable[[U], LazyHybridGroup[U]]:
        """Decorator to add a child subgroup to this group.

        Returns:
            A decorator that wraps the function in a [`LazyHybridGroup`][] and registers it.
        """

        def decorator(func: U) -> LazyHybridGroup[U]:
            child = LazyHybridGroup(func, args, kwargs)
            self.children.append(child)
            return child

        return decorator


def lazy_hybrid_command[T: Co](*args: Any, **kwargs: Any) -> Callable[[T], LazyHybridCommand[T]]:
    """Return a decorator that wraps a function in a [`LazyHybridCommand`][].

    Arguments are forwarded verbatim to `commands.hybrid_command` when the cog loads.
    """

    def decorator(func: T) -> LazyHybridCommand[T]:
        return LazyHybridCommand(func, args, kwargs)

    return decorator


def lazy_hybrid_group[T: Co](*args: Any, **kwargs: Any) -> Callable[[T], LazyHybridGroup[T]]:
    """Return a decorator that wraps a function in a [`LazyHybridGroup`][].

    Arguments are forwarded verbatim to `commands.hybrid_group` when the cog loads.
    """

    def decorator(func: T) -> LazyHybridGroup[T]:
        return LazyHybridGroup(func, args, kwargs)

    return decorator


def wrap[T](dpy_func: Any, *args: Any, **kwargs: Any) -> Callable[[T], T]:
    """Attach a discord.py decorator to a [`LazyHybridCommand`][] or plain function.

    Defers application until the cog loads, so decorators that inspect `__qualname__`
    see the correct name.

    Args:
        dpy_func: The discord.py decorator factory (e.g. `app_commands.describe`).
        *args: Positional arguments forwarded to `dpy_func`.
        **kwargs: Keyword arguments forwarded to `dpy_func`.

    Returns:
        A decorator that stores `dpy_func(*args, **kwargs)` for deferred application.

    Example:
        ```python
        @wrap(commands.has_permissions, manage_messages=True)
        @lazy_hybrid_command()
        async def example(ctx): ...
        ```
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
    """Restrict a command to channels that are currently-open Modmail ticket channels.

    Applies `guild_only` and raises [`NotInTicketError`][] when the invoking channel is
    not an open ticket, or [`StaffGuildNotConfiguredError`][] when Modmail is not configured.

    Returns:
        A compound decorator that registers the channel check.
    """

    async def predicate(ctx: Context) -> bool:
        """Return `True` when the command is invoked inside an open Modmail ticket channel.

        Raises:
            StaffGuildNotConfiguredError: If Modmail is not configured.
            NotInTicketError: If the channel is not an open ticket.
        """
        if not ctx.bot.staff_guild.is_setup():
            raise StaffGuildNotConfiguredError("Modmail is not configured.")

        if ctx.guild is None or ctx.guild.id != ctx.bot.staff_guild.guild_id:
            raise NotInTicketError("This command can only be used in Modmail tickets.")

        ticket_model = await ctx.bot.database_client.get_ticket_by_channel(ctx.channel.id, only_open=True)
        if ticket_model is None:
            raise NotInTicketError("This command can only be used in Modmail tickets.")
        return True

    return wrap(commands.guild_only)(wrap(lambda: commands.check(predicate)))


class Cog(commands.Cog, group_auto_locale_strings=False):
    """Base class for all Modmail cogs."""

    renamed_command_keys: ClassVar[list[tuple[str, str]]] = []
    """Old-to-new override key pairs for renamed callbacks. Add an entry when renaming a callback;
    remove it after 2-3 version bumps once all profiles have been migrated."""

    def __init__(self, bot: Bot) -> None:
        """Attach the bot instance.

        Args:
            bot: The [`Bot`][] instance this cog is attached to.
        """
        self.bot = bot
        """The [`Bot`][] instance this cog is attached to."""

    # TODO: Add a before invoke hook (here or in bot) that checks if using ctx.send()
    # and warns to use cog.send().


def create_cog(
    name: str,
    *,
    all_commands: list[LazyHybridCommand[Any]] | None = None,
    other_methods: list[Callable[..., Any]] | None = None,
    renamed_command_keys: list[tuple[str, str]] | None = None,
) -> type[Cog]:
    """Dynamically build a [`Cog`][] subclass with the given commands and methods.

    Args:
        name: Name for the new cog class.
        all_commands: [`LazyHybridCommand`][] instances to finalize and attach.
        other_methods: Additional callables attached as cog methods.
        renamed_command_keys: Old-to-new callback name pairs applied at startup
            to rewrite any stale permission override keys stored in profiles.

    Returns:
        A new [`Cog`][] subclass ready for `bot.add_cog()`.
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

    cls = type(name, (Cog,), methods, group_auto_locale_strings=False)
    if renamed_command_keys:
        cls.renamed_command_keys = renamed_command_keys
    return cls
