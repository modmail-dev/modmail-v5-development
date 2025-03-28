from __future__ import annotations

from typing import Any

from discord.ext import commands

from modmail.core.internals.command import (
    LazyHybridCommand,
    LazyHybridGroup,
    lazy_hybrid_command,
    lazy_hybrid_group,
    wrap,
)


class MockCog:
    """A mock cog for testing purposes."""

    def __init__(self) -> None:
        self.name = "MockCog"


def test_lazy_hybrid_command_creation() -> None:
    """Test creation of a LazyHybridCommand and conversion to a real command."""

    @lazy_hybrid_command()
    async def test_command(self: Any, ctx: Any) -> None:
        pass

    assert isinstance(test_command, LazyHybridCommand)

    # Get the converted real command
    commands_dict = test_command.get_commands("TestCog")

    assert len(commands_dict) == 1
    assert "test_command" in commands_dict
    assert isinstance(commands_dict["test_command"], commands.HybridCommand)


def test_lazy_hybrid_group_creation() -> None:
    """Test creation of a LazyHybridGroup and conversion to a real command group."""

    @lazy_hybrid_group()
    async def test_group(self: Any, ctx: Any) -> None:
        pass

    assert isinstance(test_group, LazyHybridGroup)
    assert test_group.callback.__name__ == "test_group"
    assert hasattr(test_group, "children")
    assert len(test_group.children) == 0

    # Get the converted real command group
    commands_dict = test_group.get_commands("TestCog")

    assert len(commands_dict) == 1
    assert "test_group" in commands_dict
    assert isinstance(commands_dict["test_group"], commands.HybridGroup)


def test_lazy_hybrid_group_with_children() -> None:
    """Test that LazyHybridGroup properly manages child commands and nested groups."""

    @lazy_hybrid_group()
    async def parent_group(self: Any, ctx: Any) -> None:
        pass

    @parent_group.command()
    async def child_command(self: Any, ctx: Any) -> None:  # pyright: ignore [reportUnusedFunction]
        pass

    @parent_group.group()
    async def child_group(self: Any, ctx: Any) -> None:
        pass

    @child_group.command()
    async def grandchild_command(self: Any, ctx: Any) -> None:  # pyright: ignore [reportUnusedFunction]
        pass

    assert isinstance(parent_group, LazyHybridGroup)
    assert len(parent_group.children) == 2

    # Verify children structure
    assert isinstance(parent_group.children[0], LazyHybridCommand)
    assert parent_group.children[0].callback.__name__ == "child_command"

    assert isinstance(parent_group.children[1], LazyHybridGroup)
    assert parent_group.children[1].callback.__name__ == "child_group"

    assert len(parent_group.children[1].children) == 1
    assert parent_group.children[1].children[0].callback.__name__ == "grandchild_command"

    # Get all converted commands from the parent group
    commands_dict = parent_group.get_commands("TestCog")

    # Verify command hierarchy is preserved
    assert len(commands_dict) == 4
    assert "parent_group" in commands_dict
    assert "child_command" in commands_dict
    assert "child_group" in commands_dict
    assert "grandchild_command" in commands_dict
    assert commands_dict["grandchild_command"].parent == commands_dict["child_group"]
    assert commands_dict["grandchild_command"].qualified_name == "parent_group child_group grandchild_command"


def test_wrap_decorator() -> None:
    """Test that wrap decorator properly attaches check functions to commands."""

    def has_permission() -> bool:
        return True

    @wrap(commands.check, has_permission)
    @lazy_hybrid_command()
    async def test_command(self: Any, ctx: Any) -> None:
        pass

    # Verify wrapper metadata was stored
    assert hasattr(test_command, "wrappers")
    assert any(
        wrapper_func == commands.check and wrapper_args[0] == has_permission
        for wrapper_func, wrapper_args, _ in test_command.wrappers
    )


def test_wrap_decorator_on_regular_function() -> None:
    """Test wrap decorator stores metadata when applied to non-command functions."""

    @wrap(commands.has_permissions, administrator=True)
    async def regular_function(self: Any, ctx: Any) -> None:
        pass

    # Verify metadata storage mechanism for regular functions
    assert hasattr(regular_function, "__modmail_wrappers__")
    assert len(regular_function.__modmail_wrappers__) == 1
    wrapper_func, _, wrapper_kwargs = regular_function.__modmail_wrappers__[0]
    assert wrapper_func == commands.has_permissions
    assert wrapper_kwargs == {"administrator": True}


def test_multiple_wrappers() -> None:
    """Test that multiple decorators can be stacked and are applied in correct order."""

    @wrap(commands.has_permissions, manage_messages=True)
    @wrap(commands.cooldown, 1, 5.0)
    @lazy_hybrid_command()
    async def test_command(self: Any, ctx: Any) -> None:
        pass

    # Verify both wrappers were stored
    assert any(
        wrapper_func == commands.cooldown and wrapper_args == (1, 5.0)
        for wrapper_func, wrapper_args, _ in test_command.wrappers
    )

    assert any(
        wrapper_func == commands.has_permissions and wrapper_kwargs == {"manage_messages": True}
        for wrapper_func, _, wrapper_kwargs in test_command.wrappers
    )


def test_qualname_injection() -> None:
    """Test that cog name is injected into callback's __qualname__ for proper command registration."""

    @lazy_hybrid_command()
    async def test_command(self: Any, ctx: Any) -> None:
        pass

    # Trigger qualname injection by generating commands
    test_command.get_commands("TestCog")

    # Verify the __qualname__ was updated with cog name
    assert test_command.callback.__qualname__ == "TestCog.test_command"


def test_lazy_hybrid_command_with_args_and_kwargs() -> None:
    """Test command arguments and parameters are properly passed to the real command."""

    @lazy_hybrid_command(name="custom_name", description="Custom description")
    async def test_command(self: Any, ctx: Any) -> None:
        pass

    cog = MockCog()
    command = test_command.get_commands(cog.name)["test_command"]

    # Verify parameters were properly transferred
    assert command.name == "custom_name"
    assert command.description == "Custom description"
    assert command.qualified_name == "custom_name"


def test_lazy_hybrid_group_command_and_group_methods() -> None:
    """Test that LazyHybridGroup properly handles child command and group creation methods."""

    @lazy_hybrid_group()
    async def test_group(self: Any, ctx: Any) -> None:
        """Test group docstring."""

    # Add command with custom parameters
    @test_group.command("cmd", description="Command description")
    async def group_command(self: Any, ctx: Any, param: str) -> None:  # pyright: ignore [reportUnusedFunction]
        pass

    # Add subgroup with custom parameters
    @test_group.group("sub", description="Subgroup description")
    async def group_subgroup(self: Any, ctx: Any) -> None:  # pyright: ignore [reportUnusedFunction]
        pass

    assert len(test_group.children) == 2

    # Find children by their types
    command_child = None
    group_child = None

    for child in test_group.children:
        if isinstance(child, LazyHybridCommand) and not isinstance(child, LazyHybridGroup):  # pyright: ignore [reportUnnecessaryIsInstance]
            command_child = child
        elif isinstance(child, LazyHybridGroup):  # pyright: ignore [reportUnnecessaryIsInstance]
            group_child = child

    assert command_child is not None, "Command child not found"
    assert group_child is not None, "Group child not found"

    # Verify command parameters were stored
    assert command_child.args == ("cmd",)
    assert command_child.kwargs.get("description") == "Command description"

    # Verify group parameters were stored
    assert group_child.args == ("sub",)
    assert group_child.kwargs.get("description") == "Subgroup description"


def test_wrap_decorator_with_lazy_hybrid_command() -> None:
    """Test wrap decorator properly applies to lazy hybrid commands and persists after conversion."""

    @lazy_hybrid_command()
    @wrap(commands.has_permissions, administrator=True)
    async def test_command(self: Any, ctx: Any) -> None:
        pass

    assert isinstance(test_command, LazyHybridCommand)
    assert len(test_command.wrappers) > 0

    # Verify the specific wrapper was added
    found_wrapper = False
    for wrapper_func, _, wrapper_kwargs in test_command.wrappers:
        if wrapper_func == commands.has_permissions and wrapper_kwargs == {"administrator": True}:
            found_wrapper = True
            break

    assert found_wrapper, "Wrapper was not properly added to the LazyHybridCommand"

    # Get the real command and verify checks were applied
    commands_dict = test_command.get_commands("TestCog")
    command = commands_dict["test_command"]

    assert any(check.__qualname__.startswith("has_permissions") for check in command.checks), (
        "has_permissions check was not found in the final command"
    )
