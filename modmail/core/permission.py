"""
modmail.core.permission
=======================
Contains decorators for setting access levels on commands.
These decorators are used to restrict command usage to users with specific access levels.
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine, TypeAlias, TypeVar

from discord.ext import commands

from ..enum import RequiredAccessLevel
from .internals import LazyHybridCommand

Co: TypeAlias = Callable[..., Coroutine[Any, Any, Any]]
T = TypeVar("T", bound=commands.Command[Any, Any, Any] | LazyHybridCommand[Any] | Co)

__all__ = ["staff_only", "manager_only", "admin_only", "owner_only"]


def _set_access_level(func: T, access_level: RequiredAccessLevel) -> T:
    """
    Set the default required access level for the function.
    Injects __permission__ into the command callback function.

    :param func: A command or function to set the permission level for.
    :param access_level: The access level to set.
    :return: Returns back func.
    """
    # Lots of type ignore here because we are using function injection to set the access level.
    if isinstance(func, commands.Command | LazyHybridCommand):  # Inject into the command callback
        func.callback.__permission__ = (
            access_level  # pyright: ignore [reportUnknownMemberType, reportFunctionMemberAccess]
        )
    else:  # Inject into the function itself
        func.__permission__ = access_level  # pyright: ignore [reportFunctionMemberAccess]
    return func  # pyright: ignore [reportUnknownVariableType, reportReturnType]


def staff_only(func: T) -> T:
    """
    Decorator to set the access level to staff.

    :param func: A command or function to set the access level for.
    :return: Returns back func.
    """
    return _set_access_level(func, RequiredAccessLevel.staff)


def manager_only(func: T) -> T:
    """
    Decorator to set the access level to manager.

    :param func: A command or function to set the access level for.
    :return: Returns back func.
    """
    return _set_access_level(func, RequiredAccessLevel.manager)


def admin_only(func: T) -> T:
    """
    Decorator to set the access level to admin.

    :param func: A command or function to set the access level for.
    :return: Returns back func.
    """
    return _set_access_level(func, RequiredAccessLevel.admin)


def owner_only(func: T) -> T:
    """
    Decorator to set the access level to owner.

    :param func: A command or function to set the access level for.
    :return: Returns back func.
    """
    return _set_access_level(func, RequiredAccessLevel.owner)
