from __future__ import annotations

from typing import Any

from discord.ext import commands
from pytest_mock import MockFixture

from modmail.core import lazy_hybrid_command
from modmail.core.permission import admin_only, manager_only, owner_only, staff_only
from modmail.enum import RequiredAccessLevel


def test_permission_decorators() -> None:
    """Test that the permission decorators correctly sets the permission level on functions."""

    @staff_only
    async def test_func_staff() -> None:
        pass

    assert hasattr(test_func_staff, "__permission__")
    assert test_func_staff.__permission__ == RequiredAccessLevel.staff

    @manager_only
    async def test_func_manager() -> None:
        pass

    assert hasattr(test_func_manager, "__permission__")
    assert test_func_manager.__permission__ == RequiredAccessLevel.manager

    @admin_only
    async def test_func_admin() -> None:
        pass

    assert hasattr(test_func_admin, "__permission__")
    assert test_func_admin.__permission__ == RequiredAccessLevel.admin

    @owner_only
    async def test_func_owner() -> None:
        pass

    assert hasattr(test_func_owner, "__permission__")
    assert test_func_owner.__permission__ == RequiredAccessLevel.owner


def test_permission_decorators_command() -> None:
    """Test that the permission decorators correctly sets the permission level on commands."""

    @staff_only
    @commands.command()
    async def test_cmd_staff(ctx: commands.Context[Any]) -> None:
        pass

    assert hasattr(test_cmd_staff.callback, "__permission__")
    assert test_cmd_staff.callback.__permission__ == RequiredAccessLevel.staff

    @manager_only
    @commands.command()
    async def test_cmd_manager(ctx: commands.Context[Any]) -> None:
        pass

    assert hasattr(test_cmd_manager.callback, "__permission__")
    assert test_cmd_manager.callback.__permission__ == RequiredAccessLevel.manager

    @admin_only
    @commands.command()
    async def test_cmd_admin(ctx: commands.Context[Any]) -> None:
        pass

    assert hasattr(test_cmd_admin.callback, "__permission__")
    assert test_cmd_admin.callback.__permission__ == RequiredAccessLevel.admin

    @owner_only
    @commands.command()
    async def test_cmd_owner(ctx: commands.Context[Any]) -> None:
        pass

    assert hasattr(test_cmd_owner.callback, "__permission__")
    assert test_cmd_owner.callback.__permission__ == RequiredAccessLevel.owner


def test_permission_with_lazy_hybrid_command(mocker: MockFixture) -> None:
    """Test that permission decorators work with LazyHybridCommand objects."""

    @admin_only
    @lazy_hybrid_command()
    async def lazy_cmd(self: Any, ctx: commands.Context[Any]) -> None:
        pass

    assert hasattr(lazy_cmd.callback, "__permission__")
    assert lazy_cmd.callback.__permission__ == RequiredAccessLevel.admin

    @lazy_hybrid_command()
    @manager_only
    async def lazy_cmd_after(self: Any, ctx: commands.Context[Any]) -> None:
        pass

    assert hasattr(lazy_cmd_after.callback, "__permission__")
    assert lazy_cmd_after.callback.__permission__ == RequiredAccessLevel.manager


def test_decorator_order_with_command() -> None:
    """Test that permission decorators work regardless of decorator application order."""

    @commands.command()
    @admin_only
    async def after_order(ctx: commands.Context[Any]) -> None:
        pass

    assert hasattr(after_order.callback, "__permission__")
    assert after_order.callback.__permission__ == RequiredAccessLevel.admin

    @manager_only
    @commands.command()
    async def before_order(ctx: commands.Context[Any]) -> None:
        pass

    assert hasattr(before_order.callback, "__permission__")
    assert before_order.callback.__permission__ == RequiredAccessLevel.manager
