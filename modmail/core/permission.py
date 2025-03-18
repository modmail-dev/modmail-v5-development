"""
modmail.core.permission
=======================
Contains decorators for setting permission levels on commands.
These decorators are used to restrict command usage to users with specific permission levels.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Coroutine, TypeAlias, TypeVar

from discord.ext import commands

from ..enum import PermissionRequiredLevel

if TYPE_CHECKING:
    from .commands import LazyHybridCommand

Co: TypeAlias = Callable[..., Coroutine[Any, Any, Any]]
T = TypeVar("T", bound=commands.Command[Any, Any, Any] | LazyHybridCommand[Any] | Co)

__all__ = ["staff_only", "manager_only", "admin_only", "owner_only"]


def _set_permission(func: T, permission: PermissionRequiredLevel) -> T:
    """
    Set the default required permission level for the function.
    Injects __permission__ into the command callback function.

    :param func: A command or function to set the permission level for.
    :param permission: The permission level to set.
    :return: Returns back func.
    """
    # Lots of type ignore here because we are using function injection to set the permission level.
    if isinstance(func, commands.Command | LazyHybridCommand):  # Inject into the command callback
        func.callback.__permission__ = permission  # type: ignore[reportUnknownMemberType,reportFunctionMemberAccess]
    else:  # Inject into the function itself
        func.__permission__ = permission  # type: ignore[reportUnknownMemberType]
    return func  # type: ignore[reportUnknownVariableType,reportReturnType]


def staff_only(func: T) -> T:
    """
    Decorator to set the permission level to staff.

    :param func: A command or function to set the permission level for.
    :return: Returns back func.
    """
    return _set_permission(func, PermissionRequiredLevel.staff)


def manager_only(func: T) -> T:
    """
    Decorator to set the permission level to manager.

    :param func: A command or function to set the permission level for.
    :return: Returns back func.
    """
    return _set_permission(func, PermissionRequiredLevel.manager)


def admin_only(func: T) -> T:
    """
    Decorator to set the permission level to admin.

    :param func: A command or function to set the permission level for.
    :return: Returns back func.
    """
    return _set_permission(func, PermissionRequiredLevel.admin)


def owner_only(func: T) -> T:
    """
    Decorator to set the permission level to owner.

    :param func: A command or function to set the permission level for.
    :return: Returns back func.
    """
    return _set_permission(func, PermissionRequiredLevel.owner)
