"""[`Cog`][] base class, [`create_cog`][] factory, and bot command machinery."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import discord
from discord.ext import commands

from ..config import config
from ..errors import BadPermissionsError, NotInTicketError, StaffGuildNotConfiguredError

if TYPE_CHECKING:
    from discord.app_commands import locale_str

    from .bot import Bot
    from .context import Context

__all__ = [
    "Cog",
    "CommandBuilder",
    "GroupBuilder",
    "ParamInfo",
    "bot_command",
    "bot_group",
    "create_cog",
    "in_modmail_ticket",
    "wrap",
]


type Co = Callable[..., Coroutine[Any, Any, Any]]
type DecoFactory[T: Co] = Callable[
    ..., Callable[[T], T]
]  # A deco factory that takes any arguments and returns a decorator
type HcHg = commands.HybridCommand[Any, Any, Any] | commands.HybridGroup[Any, Any, Any]


@dataclass
class ParamInfo:
    """Localized name and description for a single command parameter.

    Attributes:
        name: Localized display name for the parameter (shown on Discord for slash commands).
        description: Localized description shown in slash command tooltips and the help browser.
    """

    name: locale_str | str
    description: locale_str | str


class CommandBuilder[T: Co]:
    """Deferred wrapper around a hybrid command callback.

    Stores the callback and its decorators without creating a command object, so the cog
    name can be injected into `__qualname__` at load time via [`get_commands`][].

    Attributes:
        base_func: Constructor used to build the command; defaults to `commands.hybrid_command`,
            overridden to the parent group's `.command` or `.group` method by
            [`GroupBuilder.get_commands`][].
        callback: The original async function passed to the decorator.
        args: Positional arguments forwarded to the command constructor.
        kwargs: Keyword arguments forwarded to the command constructor.
        wrappers: Deferred decorators (e.g. `commands.has_permissions`) applied inside
            [`get_commands`][].
        param_info: Per-parameter localized name and description, keyed by Python parameter name.
        help_text: Localized long help text shown in the interactive help browser (`None` to omit).
    """

    __slots__ = ("args", "base_func", "callback", "help_text", "kwargs", "param_info", "wrappers")

    def __init__(
        self,
        func: T,
        args: Any,
        kwargs: Any,
        *,
        param_info: dict[str, ParamInfo] | None = None,
        help_text: locale_str | str | None = None,
    ) -> None:
        """Store the callback and its constructor arguments for deferred command creation.

        Args:
            func: The async function that becomes the command callback.
            args: Positional arguments forwarded to `commands.hybrid_command`.
            kwargs: Keyword arguments forwarded to `commands.hybrid_command`.
            param_info: Per-parameter localized names and descriptions.
            help_text: Localized long help text shown in the interactive help browser.
        """
        self.base_func: Callable[..., Callable[[T], HcHg]] = commands.hybrid_command
        self.callback = func
        self.args = args
        self.kwargs = kwargs
        self.param_info: dict[str, ParamInfo] = param_info or {}
        self.help_text: locale_str | str = help_text or ""

        # Store the wrappers for the command (discord.py's command decorators)
        if hasattr(func, "__modmail_wrappers__"):
            self.wrappers: list[tuple[DecoFactory[T], tuple[Any, ...], dict[str, Any]]] = func.__modmail_wrappers__  # pyright: ignore [reportFunctionMemberAccess]
        else:
            self.wrappers = []

        # All the commands should be used in guilds only
        self.wrappers.append((commands.guild_only, (), {}))

        # Set the default permissions for the slash command
        if config.permission.slash_minimum_permission_int != 0:
            self.wrappers.append((
                discord.app_commands.default_permissions,
                (discord.Permissions(config.permission.slash_minimum_permission_int),),
                {},
            ))

    @property
    def _callback_name(self) -> str:
        """The callback's function name, used as the command name."""
        return self.callback.__name__

    def get_commands(self, cog_name: str) -> dict[str, HcHg]:
        """Inject `cog_name` into `__qualname__`, apply wrappers, and return the command dict.

        Automatically applies `app_commands.rename` and `app_commands.describe` from
        [`param_info`][] before any other wrappers, then stores `param_info` on the
        created command for the help system to read.

        Args:
            cog_name: Name of the cog that will own this command.

        Returns:
            Mapping of callback name to the constructed [`commands.HybridCommand`][].
        """
        # Set the __qualname__ of the function to include the cog name
        if not self.callback.__qualname__.startswith(f"{cog_name}."):
            self.callback.__qualname__ = f"{cog_name}.{self._callback_name}"

        func = self.callback

        # Store these to the callback (cannot store to the Command since Command isn't persisted)
        vars(func)["_bot_help"] = self.help_text
        vars(func)["_bot_param_info"] = self.param_info

        # Apply param renames and descriptions from param_info
        if self.param_info:
            rename_kw = {n: i.name for n, i in self.param_info.items()}
            desc_kw = {n: i.description for n, i in self.param_info.items()}
            if rename_kw:
                func = discord.app_commands.rename(**rename_kw)(func)
            if desc_kw:
                func = discord.app_commands.describe(**desc_kw)(func)

        # Apply remaining wrappers
        for wrapper_func, wrapper_args, wrapper_kwargs in self.wrappers:
            func = wrapper_func(*wrapper_args, **wrapper_kwargs)(func)

        # Create the command using the base function (hybrid_command/hybrid_group)
        command = self.base_func(*self.args, **self.kwargs)(func)

        return {self._callback_name: command}


class GroupBuilder[T: Co](CommandBuilder[T]):
    """[`CommandBuilder`][] that owns child commands and subgroups."""

    __slots__ = ("children",)

    def __init__(
        self,
        func: T,
        args: Any,
        kwargs: Any,
        *,
        param_info: dict[str, ParamInfo] | None = None,
        help_text: locale_str | str | None = None,
    ) -> None:
        """Store the callback and constructor arguments; initialize `children` to empty.

        Args:
            func: The async function that becomes the group callback.
            args: Positional arguments forwarded to `commands.hybrid_group`.
            kwargs: Keyword arguments forwarded to `commands.hybrid_group`.
            param_info: Per-parameter localized names and descriptions for the group callback.
            help_text: Localized long help text shown in the interactive help browser.
        """
        super().__init__(func, args, kwargs, param_info=param_info, help_text=help_text)
        self.base_func: Callable[..., Callable[[T], HcHg]] = commands.hybrid_group
        self.children: list[CommandBuilder[Any]] = []
        """Child commands and subgroups registered under this group."""

    def get_commands(self, cog_name: str) -> dict[str, HcHg]:
        """Build this group then recursively build all children.

        Args:
            cog_name: Name of the cog that will own this group.

        Returns:
            Mapping of callback name to command object for this group and all descendants.

        Raises:
            TypeError: If a child is not a [`CommandBuilder`][] or [`GroupBuilder`][].
        """
        # Get the hybrid group of the func
        command_mapping = super().get_commands(cog_name)
        group = command_mapping[self._callback_name]
        assert isinstance(group, commands.HybridGroup), "Expected a HybridGroup"

        for child in self.children:
            # Change the base_func of the child to the group's
            if isinstance(child, GroupBuilder):
                child.base_func = group.group
            elif isinstance(child, CommandBuilder):  # pyright: ignore [reportUnnecessaryIsInstance]
                child.base_func = group.command
            else:
                raise TypeError(f"Unexpected child type: {type(child)}")  # pragma: no cover
            # Add the child to the command mapping
            child_command_mapping = child.get_commands(cog_name)
            command_mapping.update(child_command_mapping)
        return command_mapping

    def command[U: Co](
        self,
        *args: Any,
        help: locale_str | str | None = None,  # noqa: A002
        param_info: dict[str, ParamInfo] | None = None,
        **kwargs: Any,
    ) -> Callable[[U], CommandBuilder[U]]:
        """Decorator to add a child command to this group.

        Args:
            help: Localized long help text shown in the interactive help browser.
            param_info: Per-parameter localized names and descriptions for the callback.
            *args: Positional arguments forwarded to [`CommandBuilder`][].
            **kwargs: Keyword arguments forwarded to [`CommandBuilder`][].

        Returns:
            A decorator that wraps the function in a [`CommandBuilder`][] and registers it.
        """

        def decorator(func: U) -> CommandBuilder[U]:
            child = CommandBuilder(func, args, kwargs, param_info=param_info, help_text=help)
            self.children.append(child)
            return child

        return decorator

    def group[U: Co](
        self,
        *args: Any,
        help: locale_str | str | None = None,  # noqa: A002
        param_info: dict[str, ParamInfo] | None = None,
        **kwargs: Any,
    ) -> Callable[[U], GroupBuilder[U]]:
        """Decorator to add a child subgroup to this group.

        Args:
            help: Localized long help text shown in the interactive help browser.
            param_info: Per-parameter localized names and descriptions for the callback.
            *args: Positional arguments forwarded to [`GroupBuilder`][].
            **kwargs: Keyword arguments forwarded to [`GroupBuilder`][].

        Returns:
            A decorator that wraps the function in a [`GroupBuilder`][] and registers it.
        """

        def decorator(func: U) -> GroupBuilder[U]:
            child = GroupBuilder(func, args, kwargs, param_info=param_info, help_text=help)
            self.children.append(child)
            return child

        return decorator


def bot_command[T: Co](
    *args: Any,
    help: locale_str | str | None = None,  # noqa: A002
    param_info: dict[str, ParamInfo] | None = None,
    **kwargs: Any,
) -> Callable[[T], CommandBuilder[T]]:
    """Return a decorator that wraps a function in a [`CommandBuilder`][].

    Args:
        help: Localized long help text shown in the interactive help browser.
        param_info: Per-parameter localized names and descriptions for the callback.
        *args: Positional arguments for [`CommandBuilder`][].
        **kwargs: Keyword arguments for [`CommandBuilder`][].
    """

    def decorator(func: T) -> CommandBuilder[T]:
        return CommandBuilder(func, args, kwargs, param_info=param_info, help_text=help)

    return decorator


def bot_group[T: Co](
    *args: Any,
    help: locale_str | str | None = None,  # noqa: A002
    param_info: dict[str, ParamInfo] | None = None,
    **kwargs: Any,
) -> Callable[[T], GroupBuilder[T]]:
    """Return a decorator that wraps a function in a [`GroupBuilder`][].

    Args:
        help: Localized long help text shown in the interactive help browser.
        param_info: Per-parameter localized names and descriptions for the callback.
        *args: Positional arguments for [`GroupBuilder`][].
        **kwargs: Keyword arguments for [`GroupBuilder`][].
    """

    def decorator(func: T) -> GroupBuilder[T]:
        return GroupBuilder(func, args, kwargs, param_info=param_info, help_text=help)

    return decorator


def wrap[T](dpy_func: Any, *args: Any, **kwargs: Any) -> Callable[[T], T]:
    """Attach a discord.py decorator to a [`CommandBuilder`][] or plain function.

    Defers application until the cog loads, so decorators that inspect `__qualname__`
    see the correct name.

    Note:
        Prefer `param_info=` in [`bot_command`][] / [`bot_group`][] over `wrap` for
        `app_commands.rename` and `app_commands.describe` — those are handled automatically
        when [`ParamInfo`][] is supplied.

    Args:
        dpy_func: The discord.py decorator factory (e.g. `commands.has_permissions`).
        *args: Positional arguments forwarded to `dpy_func`.
        **kwargs: Keyword arguments forwarded to `dpy_func`.

    Returns:
        A decorator that stores `dpy_func(*args, **kwargs)` for deferred application.

    Example:
        ```python
        @wrap(commands.has_permissions, manage_messages=True)
        @bot_command()
        async def example(ctx): ...
        ```
    """

    def decorator(func: T) -> T:
        # If the function is already a lazy class
        if isinstance(func, CommandBuilder):
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
            BadPermissionsError: If the bot is missing required permissions in the ticket channel.
        """
        if not ctx.bot.staff_guild.is_setup():
            raise StaffGuildNotConfiguredError("Modmail is not configured.")

        if ctx.guild is None or ctx.guild.id != ctx.bot.staff_guild.guild_id:
            raise NotInTicketError("This command can only be used in Modmail tickets.")

        perms = ctx.channel.permissions_for(ctx.me)  # pyright: ignore [reportArgumentType]
        missing = ~perms & ctx.bot.staff_guild.MIN_PERMISSIONS
        if missing.value:
            raise BadPermissionsError(channel=ctx.channel, missing=missing)

        ticket_model = await ctx.bot.db.get_ticket_by_channel(ctx.channel.id, only_open=True)
        if ticket_model is None:
            raise NotInTicketError("This command can only be used in Modmail tickets.")

        return True

    return wrap(lambda: commands.check(predicate))


class Cog(commands.Cog, group_auto_locale_strings=False):
    """Base class for all Modmail cogs."""

    renamed_command_keys: ClassVar[list[tuple[str, str]]] = []
    """Old-to-new override key pairs for renamed callbacks. Add an entry when renaming a callback;
    remove it after 2-3 version bumps once all profiles have been migrated."""

    help_name: ClassVar[locale_str | str | None] = None
    """Localized display name for this cog in the help overview (`None` falls back to the class name)."""

    help_description: ClassVar[locale_str | str | None] = None
    """Short description shown in the help overview select (`None` to show no description)."""

    help_color: ClassVar[discord.Color | None] = None
    """Accent color used in the help command's category card (`None` for default gray)."""

    def __init__(self, bot: Bot) -> None:
        """Attach the bot instance.

        Args:
            bot: The [`Bot`][] instance this cog is attached to.
        """
        self.bot = bot
        """The [`Bot`][] instance this cog is attached to."""


def create_cog(
    name: str,
    *,
    all_commands: list[CommandBuilder[Any]] | None = None,
    other_methods: list[Callable[..., Any]] | None = None,
    renamed_command_keys: list[tuple[str, str]] | None = None,
    help_name: locale_str | str | None = None,
    help_description: locale_str | str | None = None,
    help_color: discord.Color | None = None,
) -> type[Cog]:
    """Dynamically build a [`Cog`][] subclass with the given commands and methods.

    Args:
        name: Name for the new cog class.
        all_commands: [`CommandBuilder`][] instances to finalize and attach.
        other_methods: Additional callables attached as cog methods.
        renamed_command_keys: Old-to-new callback name pairs applied at startup
            to rewrite any stale permission override keys stored in profiles.
        help_color: Accent color for this cog's card in the help command.
        help_name: Localized display name shown in the help overview.
        help_description: Short description shown in the help overview select.

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
    if help_name is not None:
        cls.help_name = help_name
    if help_description is not None:
        cls.help_description = help_description
    if help_color is not None:
        cls.help_color = help_color
    return cls
