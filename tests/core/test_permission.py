from __future__ import annotations

from typing import Any

from discord.ext import commands
from pytest_mock import MockFixture

from modmail.core.internals import LazyHybridCommand
from modmail.core.permission import admin_only, manager_only, owner_only, staff_only
from modmail.enum import RequiredAccessLevel


def test_staff_only_function() -> None:
    """Test that staff_only decorator correctly sets the permission level on functions."""

    @staff_only
    async def test_func() -> None:
        pass

    assert hasattr(test_func, "__permission__")
    assert test_func.__permission__ == RequiredAccessLevel.staff


def test_manager_only_function() -> None:
    """Test that manager_only decorator correctly sets the permission level on functions."""

    @manager_only
    async def test_func() -> None:
        pass

    assert hasattr(test_func, "__permission__")
    assert test_func.__permission__ == RequiredAccessLevel.manager


def test_admin_only_function() -> None:
    """Test that admin_only decorator correctly sets the permission level on functions."""

    @admin_only
    async def test_func() -> None:
        pass

    assert hasattr(test_func, "__permission__")
    assert test_func.__permission__ == RequiredAccessLevel.admin


def test_owner_only_function() -> None:
    """Test that owner_only decorator correctly sets the permission level on functions."""

    @owner_only
    async def test_func() -> None:
        pass

    assert hasattr(test_func, "__permission__")
    assert test_func.__permission__ == RequiredAccessLevel.owner


def test_staff_only_command() -> None:
    """Test that staff_only decorator correctly sets the permission level on commands."""

    @staff_only
    @commands.command()
    async def test_cmd(_: Any) -> None:
        pass

    assert hasattr(test_cmd.callback, "__permission__")
    assert test_cmd.callback.__permission__ == RequiredAccessLevel.staff


def test_manager_only_command() -> None:
    """Test that manager_only decorator correctly sets the permission level on commands."""

    @manager_only
    @commands.command()
    async def test_cmd(_: Any) -> None:
        pass

    assert hasattr(test_cmd.callback, "__permission__")
    assert test_cmd.callback.__permission__ == RequiredAccessLevel.manager


def test_admin_only_command() -> None:
    """Test that admin_only decorator correctly sets the permission level on commands."""

    @admin_only
    @commands.command()
    async def test_cmd(_: Any) -> None:
        pass

    assert hasattr(test_cmd.callback, "__permission__")
    assert test_cmd.callback.__permission__ == RequiredAccessLevel.admin


def test_owner_only_command() -> None:
    """Test that owner_only decorator correctly sets the permission level on commands."""

    @owner_only
    @commands.command()
    async def test_cmd(_: Any) -> None:
        pass

    assert hasattr(test_cmd.callback, "__permission__")
    assert test_cmd.callback.__permission__ == RequiredAccessLevel.owner


def test_permission_with_lazy_hybrid_command(mocker: MockFixture) -> None:
    """Test that permission decorators work with LazyHybridCommand objects."""

    async def callback(self: Any, _: Any) -> None:
        pass

    lazy_cmd = mocker.MagicMock(spec=LazyHybridCommand)
    lazy_cmd.callback = callback

    admin_only(lazy_cmd)

    assert hasattr(lazy_cmd.callback, "__permission__")
    assert lazy_cmd.callback.__permission__ == RequiredAccessLevel.admin


def test_decorator_order() -> None:
    """Test that permission decorators work regardless of decorator application order."""

    @commands.command()
    @admin_only
    async def after_order(_: Any) -> None:
        pass

    assert hasattr(after_order.callback, "__permission__")
    assert after_order.callback.__permission__ == RequiredAccessLevel.admin

    @admin_only
    @commands.command()
    async def before_order(_: Any) -> None:
        pass

    assert hasattr(before_order.callback, "__permission__")
    assert before_order.callback.__permission__ == RequiredAccessLevel.admin
