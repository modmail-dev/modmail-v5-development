"""
modmail.core.commands.command
=============================
This module contains a custom implementation of a lazy hybrid command decorator for Modmail's cogs.
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine, TypeVar

from discord.ext import commands

__all__ = ["LazyHybridCommand", "LazyHybridGroup", "lazy_hybrid_command", "lazy_hybrid_group", "wrap"]

T = TypeVar("T")


class LazyHybridCommand:
    """
    A class that represents a lazy hybrid command.

    Allows the injection of the cog name into the __qualname__ of the callback function.
    """

    __slot__ = ("func", "name", "args", "kwargs", "wrappers")

    base_func: Callable[..., Callable[[Callable[..., Coroutine[Any, Any, Any]]], Any]] = staticmethod(
        commands.hybrid_command
    )

    def __init__(self, func: Callable[..., Coroutine[Any, Any, Any]], args: Any, kwargs: Any):
        self.func = func
        self.name: str = func.__name__
        self.args = args
        self.kwargs = kwargs

        # Store the wrappers for the command (discord.py's command decorators)
        if hasattr(func, "__modmail_wrappers__"):
            self.wrappers: list[tuple[Callable[..., Callable[[T], T]], Any, Any]] = func.__modmail_wrappers__  # type: ignore[reportFunctionMemberAccess]
        else:
            self.wrappers = []

    def get_command(
        self, cog_name: str
    ) -> dict[str, commands.HybridCommand[Any, Any, Any] | commands.HybridGroup[Any, Any, Any]]:
        """
        Create the command with the cog name injected into the __qualname__ of the callback function.

        :param cog_name: The cog's name.
        :return: A mapping of function names to commands.
        """
        # Set the __qualname__ of the function to include the cog name
        if not self.func.__qualname__.startswith(f"{cog_name}."):
            self.func.__qualname__ = f"{cog_name}.{self.func.__name__}"

        # Apply the wrappers to the function directly (app_command decorators does not work on command)
        for wrapper in self.wrappers:
            self.func = wrapper[0](*wrapper[1], **wrapper[2])(self.func)

        # Create the command using the base function (hybrid_command/hybrid_group)
        command = self.base_func(*self.args, **self.kwargs)(self.func)

        return {self.func.__name__: command}


class LazyHybridGroup(LazyHybridCommand):
    """
    A class that represents a lazy hybrid group command.

    Allows the injection of the cog name into the __qualname__ of the callback function.
    """

    base_func = staticmethod(commands.hybrid_group)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.children: list[LazyHybridCommand] = []

    def get_command(
        self, cog_name: str
    ) -> dict[str, commands.HybridCommand[Any, Any, Any] | commands.HybridGroup[Any, Any, Any]]:
        # Get the hybrid group of the func
        command_mapping = super().get_command(cog_name)

        for child in self.children:
            # Change the base_func of the child to the group's
            if isinstance(child, LazyHybridGroup):
                child.base_func = command_mapping[self.func.__name__].group  # type: ignore[reportUnknownMemberType]
            elif isinstance(child, LazyHybridCommand):  # type: ignore[reportUnnecessaryIsInstance]
                child.base_func = command_mapping[self.func.__name__].command  # type: ignore[reportUnknownMemberType]
            else:
                raise TypeError(f"Unexpected child type: {type(child)}")
            # Add the child to the command mapping
            child_command_mapping = child.get_command(cog_name)
            command_mapping.update(child_command_mapping)
        return command_mapping

    def command(
        self, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., Coroutine[Any, Any, Any]]], LazyHybridCommand]:
        """
        Create a hybrid child command.
        Accepts the same arguments as discord.py's hybrid_command.
        """

        def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> LazyHybridCommand:
            child = LazyHybridCommand(func, args, kwargs)
            self.children.append(child)
            return child

        return decorator

    def group(
        self, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., Coroutine[Any, Any, Any]]], LazyHybridGroup]:
        """
        Create a hybrid child group.
        Accepts the same arguments as discord.py's hybrid_group.
        """

        def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> LazyHybridGroup:
            child = LazyHybridGroup(func, args, kwargs)
            self.children.append(child)
            return child

        return decorator


def lazy_hybrid_command(
    *args: Any, **kwargs: Any
) -> Callable[[Callable[..., Coroutine[Any, Any, Any]]], LazyHybridCommand]:
    """
    Store the args for hybrid_command, but don't create the actual command yet.
    This is necessary to inject the cog name into __qualname__ of the callback func later.
    Accepts the same arguments as discord.py's hybrid_command.
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> LazyHybridCommand:
        return LazyHybridCommand(func, args, kwargs)

    return decorator


def lazy_hybrid_group(
    *args: Any, **kwargs: Any
) -> Callable[[Callable[..., Coroutine[Any, Any, Any]]], LazyHybridGroup]:
    """
    Store the args for hybrid_group, but don't create the actual command yet.
    This is necessary to inject the cog name into __qualname__ of the callback func later.
    Accepts the same arguments as discord.py's hybrid_group.
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> LazyHybridGroup:
        return LazyHybridGroup(func, args, kwargs)

    return decorator


def wrap(dpy_func: Callable[..., Callable[[T], T]], *args: Any, **kwargs: Any) -> Callable[[T], T]:
    """
    A decorator that wraps a function with a discord.py command decorator.
    Example: @wrap(commands.has_permissions, manage_messages=True)
    """

    def decorator(func: T) -> T:
        if isinstance(func, LazyHybridCommand):  # If the function is already a lazy class
            func.wrappers.append((dpy_func, args, kwargs))
        else:  # Otherwise, add the wrapper to the function directly
            if not hasattr(func, "__modmail_wrappers__"):
                func.__modmail_wrappers__ = []  # type: ignore[reportFunctionMemberAccess]
            func.__modmail_wrappers__.append((dpy_func, args, kwargs))  # type: ignore[reportUnknownMemberType,reportAttributeAccessIssue]
        return func

    return decorator
