"""Contains decorators for setting access levels on commands.

These decorators are used to restrict command usage to users with specific access levels.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from discord.ext import commands

from ..enum import RequiredAccessLevel
from .internals import LazyHybridCommand

type AnyCo = commands.Command[Any, Any, Any] | LazyHybridCommand[Any] | Callable[..., Coroutine[Any, Any, Any]]

__all__ = [
    "admin_only",
    "manager_only",
    "owner_only",
    "staff_only",
]


def _set_access_level[T: AnyCo](func: T, access_level: RequiredAccessLevel) -> T:
    """Set the default required access level for the function.

    Injects __permission__ into the command callback function.

    Args:
        func: A command or function to set the permission level for.
        access_level: The access level to set.

    Returns:
        The input function with permission level set.
    """
    # Lots of type ignore here because we are using function injection to set the access level.
    if isinstance(func, commands.Command | LazyHybridCommand):  # Inject into the command callback
        func.callback.__permission__ = access_level  # pyright: ignore [reportUnknownMemberType, reportFunctionMemberAccess]
    else:  # Inject into the function itself
        func.__permission__ = access_level  # pyright: ignore [reportFunctionMemberAccess]
    return func  # pyright: ignore [reportUnknownVariableType, reportReturnType]


def staff_only[T: AnyCo](func: T) -> T:
    """Decorator to set the command access level to staff.

    Args:
        func: A command or function to set the access level for.

    Returns:
        The input function with staff permission level set.
    """
    return _set_access_level(func, RequiredAccessLevel.staff)


def manager_only[T: AnyCo](func: T) -> T:
    """Decorator to set the command access level to manager.

    Args:
        func: A command or function to set the access level for.

    Returns:
        The input function with manager permission level set.
    """
    return _set_access_level(func, RequiredAccessLevel.manager)


def admin_only[T: AnyCo](func: T) -> T:
    """Decorator to set the command access level to admin.

    Args:
        func: A command or function to set the access level for.

    Returns:
        The input function with admin permission level set.
    """
    return _set_access_level(func, RequiredAccessLevel.admin)


def owner_only[T: AnyCo](func: T) -> T:
    """Decorator to set the command access level to owner.

    Args:
        func: A command or function to set the access level for.

    Returns:
        The input function with owner permission level set.
    """
    return _set_access_level(func, RequiredAccessLevel.owner)
