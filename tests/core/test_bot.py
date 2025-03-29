from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import discord
import pytest
from discord.ext import commands
from pydantic import SecretStr
from pytest_mock import MockerFixture

from modmail.backends.common import Activity, DBClientBase, Profile, Settings
from modmail.backends.mongodb import MongoDBClient
from modmail.backends.sql import SQLClient
from modmail.config.models import MongoDBDatabaseConfig, SQLDatabaseConfig
from modmail.core import Bot
from modmail.core.permission import admin_only, owner_only
from modmail.enum import (
    AccessLevel,
    ActivityType,
    PermissionOverrideValue,
    ProfileType,
    RequiredAccessLevel,
    StatusType,
)
from modmail.errors import DatabaseError


class Context(commands.Context[Bot]):
    _perm_check_reason: str


@pytest.fixture
def mock_bot(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> Bot:
    """Return a Bot instance with key mocks for testing."""
    bot = Bot()
    mocker.patch.object(bot, "is_owner", return_value=False)
    mocker.patch.object(bot, "wait_until_ready")
    mocker.patch.object(bot, "start")
    mocker.patch.object(bot, "close")
    mocker.patch.object(bot, "database_client", spec=DBClientBase)
    mocker.patch.object(bot, "load_extension")

    # Mock application info and command tree
    app_info = mocker.MagicMock(spec=discord.AppInfo)
    app_info.bot_public = False
    monkeypatch.setattr("discord.Client.application_info", mocker.AsyncMock(return_value=app_info))

    tree = mocker.MagicMock(spec=discord.app_commands.CommandTree)
    monkeypatch.setattr("discord.ext.commands.Bot.tree", tree)

    return bot


@pytest.fixture
def context(mock_bot: Bot, mocker: MockerFixture) -> Context:
    """Return a mock command context with an admin-required command for permission tests."""
    ctx = mocker.MagicMock(spec=Context)
    ctx.bot = mock_bot
    ctx.author = mocker.MagicMock(spec=discord.Member)
    ctx.author.bot = False

    @admin_only
    @commands.command()
    async def test_func(ctx: Context) -> None:
        pass

    ctx.command = test_func
    return cast(Context, ctx)


def test_bot_init_no_prefix(mocker: MockerFixture) -> None:
    """Test bot initializes with default command prefix when not configured."""
    mocker.patch("modmail.core.bot.CONFIG.bot.prefix", None)
    bot = Bot()
    assert not bot.command_prefix  # pyright: ignore [reportUnknownMemberType]


def test_bot_init_database_clients(mocker: MockerFixture, tmp_path: Path) -> None:
    """Test bot initializes correct database clients based on configuration."""
    mocker.patch("modmail.core.bot.CONFIG.database_type", "mongodb")
    mocker.patch(
        "modmail.core.bot.CONFIG.mongodb_config",
        MongoDBDatabaseConfig(uri=cast(SecretStr, "mongodb://some-database:27017")),
    )

    bot = Bot()
    assert isinstance(bot.database_client, MongoDBClient)

    mocker.patch("modmail.core.bot.CONFIG.database_type", "sql")
    mocker.patch(
        "modmail.core.bot.CONFIG.mongodb_config",
        SQLDatabaseConfig(uri=cast(SecretStr, f"sqlite+aiosqlite:////{tmp_path.absolute() / 'some-database.db'}")),
    )  # Using tmp_path in case the file gets created/modified somehow.

    bot = Bot()
    assert isinstance(bot.database_client, SQLClient)


@pytest.mark.asyncio(loop_scope="function")
async def test_setup_hook_slash_command_syncing(mock_bot: Bot, mocker: MockerFixture) -> None:
    """Test slash command syncing/un-syncing conditions during bot setup."""
    # Mock the settings model, database_client was already mocked in the fixture
    settings_mock = mocker.MagicMock(spec=Settings)
    settings_mock.last_slash_synced_version = mock_bot.version
    settings_mock.last_ran_locale = "en"
    settings_mock.last_slash_minimum_permission_int = 0
    settings_mock.last_ran_version = mock_bot.version
    mocker.patch("modmail.core.bot.CONFIG.default_locale", "en")
    mocker.patch("modmail.core.bot.CONFIG.permission.slash_minimum_permission_int", 0)

    cast(Mock, mock_bot.database_client).settings_model = settings_mock

    # Mock sync methods
    sync_mock = mocker.patch.object(mock_bot, "_sync_slash_commands")
    unsync_mock = mocker.patch.object(mock_bot, "_unsync_slash_commands")
    update_settings_mock = mocker.patch.object(mock_bot.database_client, "update_settings")

    # Grouping conditions for force sync and unsync scenarios.
    # Test 1: Force sync with use_slash_commands = True
    mocker.patch("modmail.core.bot.CONFIG.bot.force_sync_commands", True)
    mocker.patch("modmail.core.bot.CONFIG.bot.use_slash_commands", True)
    await mock_bot.setup_hook()
    sync_mock.assert_called_once()
    unsync_mock.assert_not_called()
    sync_mock.reset_mock()
    unsync_mock.reset_mock()

    # Test 2: Force sync with use_slash_commands = False
    mocker.patch("modmail.core.bot.CONFIG.bot.force_sync_commands", True)
    mocker.patch("modmail.core.bot.CONFIG.bot.use_slash_commands", False)
    await mock_bot.setup_hook()
    sync_mock.assert_not_called()
    unsync_mock.assert_called_once()
    sync_mock.reset_mock()
    unsync_mock.reset_mock()

    # Test 3: Normal sync when version has changed
    mocker.patch("modmail.core.bot.CONFIG.bot.force_sync_commands", False)
    mocker.patch("modmail.core.bot.CONFIG.bot.use_slash_commands", True)
    settings_mock.last_slash_synced_version = "0.0"  # Different from bot version
    await mock_bot.setup_hook()
    sync_mock.assert_called_once()
    unsync_mock.assert_not_called()
    sync_mock.reset_mock()
    unsync_mock.reset_mock()

    # Test 4: No sync needed when version hasn't changed
    settings_mock.last_slash_synced_version = mock_bot.version
    await mock_bot.setup_hook()
    sync_mock.assert_not_called()
    unsync_mock.assert_not_called()

    # Test 5: Unsync when use_slash_commands is turned off but was previously on
    mocker.patch("modmail.core.bot.CONFIG.bot.use_slash_commands", False)
    settings_mock.last_slash_synced_version = "1.0"  # Not None
    await mock_bot.setup_hook()
    sync_mock.assert_not_called()
    unsync_mock.assert_called_once()
    sync_mock.reset_mock()
    unsync_mock.reset_mock()

    # Test 6: No unsync needed when already un-synced
    settings_mock.last_slash_synced_version = None
    await mock_bot.setup_hook()
    sync_mock.assert_not_called()
    unsync_mock.assert_not_called()
    settings_mock.last_slash_synced_version = mock_bot.version

    # Test 7: Locale change triggers sync
    mocker.patch("modmail.core.bot.CONFIG.bot.use_slash_commands", True)
    settings_mock.last_ran_locale = "fr"
    await mock_bot.setup_hook()
    sync_mock.assert_called_once()
    update_settings_mock.assert_any_call(last_ran_locale="en")
    sync_mock.reset_mock()
    update_settings_mock.reset_mock()
    settings_mock.last_ran_locale = "en"

    # Test 8: Permission change triggers sync
    settings_mock.last_slash_minimum_permission_int = 1
    mocker.patch("modmail.core.bot.CONFIG.permission.slash_minimum_permission_int", 2)
    await mock_bot.setup_hook()
    sync_mock.assert_called_once()
    update_settings_mock.assert_any_call(last_slash_minimum_permission_int=2)
    sync_mock.reset_mock()
    update_settings_mock.reset_mock()
    mocker.patch("modmail.core.bot.CONFIG.permission.slash_minimum_permission_int", 0)

    # Test 9: First run of locale (last_ran_locale is None)
    settings_mock.last_ran_locale = None
    await mock_bot.setup_hook()
    update_settings_mock.assert_any_call(last_ran_locale="en")

    # Test 10: First run of permission (last_slash_minimum_permission_int is None)
    settings_mock.last_slash_minimum_permission_int = None
    mocker.patch("modmail.core.bot.CONFIG.permission.slash_minimum_permission_int", 2)
    await mock_bot.setup_hook()
    update_settings_mock.assert_any_call(last_slash_minimum_permission_int=2)


@pytest.mark.asyncio(loop_scope="function")
async def test_slash_sync_unsync(mock_bot: Bot, mocker: MockerFixture) -> None:
    """Test proper syncing and un-syncing of slash commands with Discord."""
    update_settings_mock = mocker.patch.object(mock_bot.database_client, "update_settings")

    # Test syncing
    await mock_bot._sync_slash_commands()
    update_settings_mock.assert_called_once_with(last_slash_synced_version=mock_bot.version)
    update_settings_mock.reset_mock()

    # Test un-syncing
    await mock_bot._unsync_slash_commands()
    update_settings_mock.assert_called_once_with(last_slash_synced_version=None)


@pytest.mark.asyncio(loop_scope="function")
async def test_bot_permission_check_owner(mock_bot: Bot, context: Context, mocker: MockerFixture) -> None:
    """Test that bot owner bypasses permission checks."""
    mocker.patch.object(mock_bot, "is_owner", return_value=True)
    assert await mock_bot._permission_check(context), context._perm_check_reason
    assert context._perm_check_reason == "owner"


@pytest.mark.asyncio(loop_scope="function")
async def test_bot_permission_check_bot(mock_bot: Bot, context: Context) -> None:
    """Test rejection of bot accounts in permission checks."""
    context.author.bot = True
    assert not await mock_bot._permission_check(context), context._perm_check_reason
    assert context._perm_check_reason == "bot"


@pytest.mark.asyncio(loop_scope="function")
async def test_bot_permission_check_profiles(mock_bot: Bot, context: Context, mocker: MockerFixture) -> None:
    """Test permission validation using user profiles with access levels."""
    # Mock profile
    profile = mocker.MagicMock(spec=Profile)
    profile.bot_id = 123456789012345
    profile.access_level = AccessLevel.admin
    profile.profile_id = 123456789012345
    profile.profile_type = ProfileType.user
    profile.permission_overrides = {}

    # Mock get_all_user_profiles
    mocker.patch.object(mock_bot, "get_all_user_profiles", return_value=[profile])

    assert await mock_bot._permission_check(context), context._perm_check_reason
    assert str(profile.profile_id) in context._perm_check_reason


@pytest.mark.asyncio(loop_scope="function")
async def test_permission_check_with_different_access_levels(
    mock_bot: Bot, context: Context, mocker: MockerFixture
) -> None:
    """Test permission checks with varying user and command access levels."""
    # Test each access level combination

    # Create a test command with admin access level
    @admin_only  # This sets access level to admin
    @commands.command()
    async def admin_command(ctx: Context) -> None:
        pass

    context.command = admin_command

    # Test case 1: User has everyone access but command requires admin
    profile = mocker.MagicMock(spec=Profile)
    profile.bot_id = 123456789012345
    profile.access_level = AccessLevel.everyone
    profile.profile_id = 123456789012345
    profile.profile_type = ProfileType.user
    profile.permission_overrides = {}

    mocker.patch.object(mock_bot, "get_all_user_profiles", return_value=[profile])
    assert not await mock_bot._permission_check(context), context._perm_check_reason
    assert "no access" in context._perm_check_reason

    # Test case 2: User has admin access and command requires admin
    profile.access_level = AccessLevel.admin
    assert await mock_bot._permission_check(context), context._perm_check_reason
    assert str(profile.profile_id) in context._perm_check_reason

    # Create a test command with everyone access level
    @commands.command()
    async def everyone_command(ctx: Context) -> None:
        pass

    context.command = everyone_command
    profile.access_level = None

    # Test case 4: Default access for everyone commands
    mocker.patch("modmail.core.bot.CONFIG.permission.default_access_everyone", True)
    assert await mock_bot._permission_check(context), context._perm_check_reason
    assert "everyone" in context._perm_check_reason

    # Test case 5: No default access for everyone commands
    mocker.patch("modmail.core.bot.CONFIG.permission.default_access_everyone", False)
    assert not await mock_bot._permission_check(context), context._perm_check_reason
    assert "no access" in context._perm_check_reason

    # Create a test command with owner access level
    @owner_only
    @commands.command()
    async def owner_command(ctx: Context) -> None:
        pass

    context.command = owner_command
    assert not await mock_bot._permission_check(context), context._perm_check_reason
    assert "owner only" in context._perm_check_reason


@pytest.mark.asyncio(loop_scope="function")
async def test_permission_check_with_profile_overrides(
    mock_bot: Bot, context: Context, mocker: MockerFixture
) -> None:
    """Test command permission overrides as defined in user profiles."""

    # Create a test command
    @admin_only
    @commands.command()
    async def test_command(ctx: Context) -> None:
        pass

    context.command = test_command

    # Test case 1: Profile has deny override for the command
    profile = mocker.MagicMock(spec=Profile)
    profile.bot_id = 123456789012345
    profile.access_level = AccessLevel.manager
    profile.profile_id = 123456789012345
    profile.profile_type = ProfileType.user
    profile.permission_overrides = {"test": PermissionOverrideValue.deny}

    mocker.patch.object(mock_bot, "get_all_user_profiles", return_value=[profile])
    assert not await mock_bot._permission_check(context), context._perm_check_reason
    assert "deny test" in context._perm_check_reason

    # Test case 2: Profile has allow override for the command
    profile.permission_overrides = {"test": PermissionOverrideValue.allow}
    assert await mock_bot._permission_check(context), context._perm_check_reason
    assert "allow test" in context._perm_check_reason


@pytest.mark.asyncio(loop_scope="function")
async def test_permission_check_with_wildcard_overrides(
    mock_bot: Bot, context: Context, mocker: MockerFixture
) -> None:
    """Test wildcard overrides for parent commands and their subcommands."""

    # Create a parent command and subcommand
    @commands.group(name="parent")
    async def parent_command(ctx: Context) -> None:
        pass

    @admin_only
    @parent_command.command()
    async def parent_child_command(ctx: Context) -> None:
        pass

    # Set the command and its parent
    context.command = parent_child_command

    # Test case 1: Profile has deny wildcard override for the parent command
    profile = mocker.MagicMock(spec=Profile)
    profile.bot_id = 123456789012345
    profile.access_level = AccessLevel.manager
    profile.profile_id = 123456789012345
    profile.profile_type = ProfileType.user
    profile.permission_overrides = {"parent+": PermissionOverrideValue.deny}

    mocker.patch.object(mock_bot, "get_all_user_profiles", return_value=[profile])
    assert not await mock_bot._permission_check(context), context._perm_check_reason
    assert "deny parent+" in context._perm_check_reason

    # Test case 2: Profile has allow wildcard override for the parent command
    profile.permission_overrides = {"parent+": PermissionOverrideValue.allow}
    assert await mock_bot._permission_check(context), context._perm_check_reason
    assert "allow parent+" in context._perm_check_reason

    # Test case 3: Profile has conflicting overrides (specific overrides take precedence)
    profile.permission_overrides = {
        "parent+": PermissionOverrideValue.allow,
        "parent child": PermissionOverrideValue.deny,
    }
    assert not await mock_bot._permission_check(context), context._perm_check_reason
    assert "deny parent child" in context._perm_check_reason

    @owner_only
    @parent_command.command()
    async def parent_child2_command(ctx: Context) -> None:
        pass

    # Set the command and its parent
    context.command = parent_child2_command

    # Test case 4: Profile has allow wildcard override for the parent command, child is owner only
    profile.permission_overrides = {"parent+": PermissionOverrideValue.allow}
    assert not await mock_bot._permission_check(context), context._perm_check_reason
    assert "owner only" in context._perm_check_reason


@pytest.mark.asyncio(loop_scope="function")
async def test_permission_check_with_multiple_profiles(
    mock_bot: Bot, context: Context, mocker: MockerFixture
) -> None:
    """Test permission resolution when a user has multiple profiles."""

    # Create a test command with admin access level
    @admin_only
    @commands.command(name="test")
    async def test_command(ctx: Context) -> None:
        pass

    context.command = test_command

    # Create multiple profiles with different access levels
    user_profile = mocker.MagicMock(spec=Profile)
    user_profile.bot_id = 123456789012345
    user_profile.access_level = AccessLevel.everyone
    user_profile.profile_id = 123456789012345
    user_profile.profile_type = ProfileType.user
    user_profile.permission_overrides = {}

    role1_profile = mocker.MagicMock(spec=Profile)
    role1_profile.bot_id = 123456789012345
    role1_profile.access_level = None  # No access level
    role1_profile.profile_id = 222222222222222
    role1_profile.profile_type = ProfileType.role
    role1_profile.permission_overrides = {}

    role2_profile = mocker.MagicMock(spec=Profile)
    role2_profile.bot_id = 123456789012345
    role2_profile.access_level = AccessLevel.admin  # Admin access level
    role2_profile.profile_id = 333333333333333
    role2_profile.profile_type = ProfileType.role
    role2_profile.permission_overrides = {}

    # Test case 1: Multiple profiles, one with sufficient access level
    mocker.patch.object(
        mock_bot, "get_all_user_profiles", return_value=[user_profile, role1_profile, role2_profile]
    )

    assert await mock_bot._permission_check(context), context._perm_check_reason
    assert str(role2_profile.profile_id) in context._perm_check_reason

    # Test case 2: A profile has a deny override
    override_profile = mocker.MagicMock(spec=Profile)
    override_profile.bot_id = 123456789012345
    override_profile.access_level = AccessLevel.everyone
    override_profile.profile_id = 444444444444444
    override_profile.profile_type = ProfileType.role
    override_profile.permission_overrides = {"test": PermissionOverrideValue.deny}
    role2_profile.permission_overrides = {"test": PermissionOverrideValue.allow}

    # The first profile with a override should take precedence
    mocker.patch.object(mock_bot, "get_all_user_profiles", return_value=[override_profile, role2_profile])

    assert not await mock_bot._permission_check(context), context._perm_check_reason
    assert str(override_profile.profile_id) in context._perm_check_reason


def test_get_command_access_level(mock_bot: Bot, mocker: MockerFixture) -> None:
    """Test retrieval of command access levels from decorators and config overrides."""

    # Test case 1: Command with explicit access level
    @admin_only
    @commands.command()
    async def admin_command(ctx: Context) -> None:
        pass

    assert mock_bot.get_command_access_level(admin_command) == RequiredAccessLevel.admin

    # Test case 2: Command with no access level
    @commands.command()
    async def everyone_command(ctx: Context) -> None:
        pass

    assert mock_bot.get_command_access_level(everyone_command) == RequiredAccessLevel.everyone

    # Test case 3: Command with config override
    overrides = {"admin": RequiredAccessLevel.manager}
    mocker.patch("modmail.core.bot.CONFIG.permission.overrides", overrides)

    assert mock_bot.get_command_access_level(admin_command) == RequiredAccessLevel.manager

    # Test case 4: Subcommand with parent wildcard override
    @commands.group()
    async def parent_command(ctx: Context) -> None:
        pass

    @admin_only
    @parent_command.command()
    async def child_command(ctx: Context) -> None:
        pass

    overrides = {"parent+": RequiredAccessLevel.staff}
    mocker.patch("modmail.core.bot.CONFIG.permission.overrides", overrides)

    assert mock_bot.get_command_access_level(child_command) == RequiredAccessLevel.staff


def test_get_all_user_profiles(mock_bot: Bot, mocker: MockerFixture) -> None:
    """Test retrieval of user and role profiles for a given entity."""

    # Mock user and member
    user = mocker.MagicMock(spec=discord.User)
    user.id = 123456789012345

    member = mocker.MagicMock(spec=discord.Member)
    member.id = 123456789012345

    # Create roles with IDs
    role1 = mocker.MagicMock(spec=discord.Role)
    role1.id = 111111111111111

    role2 = mocker.MagicMock(spec=discord.Role)
    role2.id = 222222222222222

    # Member has roles
    member.roles = [role1, role2]

    # Create profiles
    user_profile = mocker.MagicMock(spec=Profile)
    user_profile.profile_id = 123456789012345
    user_profile.profile_type = ProfileType.user

    role1_profile = mocker.MagicMock(spec=Profile)
    role1_profile.profile_id = 111111111111111
    role1_profile.profile_type = ProfileType.role

    role2_profile = mocker.MagicMock(spec=Profile)
    role2_profile.profile_id = 222222222222222
    role2_profile.profile_type = ProfileType.role

    # Mock get_profile method
    def mock_get_profile(profile_id: int, profile_type: ProfileType) -> Profile | None:
        if profile_id == 123456789012345 and profile_type == ProfileType.user:
            return user_profile
        if profile_id == 111111111111111 and profile_type == ProfileType.role:
            return role1_profile
        if profile_id == 222222222222222 and profile_type == ProfileType.role:
            return role2_profile
        return None

    mock_bot.database_client.get_profile = mock_get_profile

    # Test case 1: Regular user (no roles)
    profiles = mock_bot.get_all_user_profiles(user)
    assert len(profiles) == 1
    assert profiles[0] == user_profile

    # Test case 2: Member with roles
    profiles = mock_bot.get_all_user_profiles(member)
    assert len(profiles) == 3
    # User profile should be first (most significant)
    assert profiles[0] == user_profile
    # Then role profiles in reverse order (most significant first)
    assert profiles[1] == role2_profile
    assert profiles[2] == role1_profile

    # Test case 3: No profiles
    def mock_get_profile_none(profile_id: int, profile_type: ProfileType) -> Profile | None:
        return None

    mock_bot.database_client.get_profile = mock_get_profile_none
    profiles = mock_bot.get_all_user_profiles(user)
    assert len(profiles) == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_setup_hook_bot_public(
    mock_bot: Bot, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that public bots are rejected unless bypass flag is enabled."""
    # Mock application info
    app_info = mocker.MagicMock(spec=discord.AppInfo)
    app_info.bot_public = True
    monkeypatch.setattr("discord.Client.application_info", mocker.AsyncMock(return_value=app_info))

    # Mock close method
    close_mock = mocker.patch.object(mock_bot, "close")

    mocker.patch("modmail.core.bot.CONFIG.bot.bypass_public_bot_check", False)
    await mock_bot.setup_hook()
    close_mock.assert_called_once()

    close_mock.reset_mock()
    mocker.patch("modmail.core.bot.CONFIG.bot.bypass_public_bot_check", True)
    await mock_bot.setup_hook()
    close_mock.assert_not_called()


@pytest.mark.asyncio(loop_scope="function")
async def test_set_and_clear_bot_presence(mock_bot: Bot, mocker: MockerFixture) -> None:
    """Test setting and clearing the bot's presence (activity and status)."""
    # Mock change_presence
    change_presence_mock = mocker.patch.object(mock_bot, "change_presence")

    # Mock database update
    db_mock = mocker.MagicMock(spec=DBClientBase)
    mock_bot.database_client = db_mock

    activity = Activity(name="test", type=ActivityType.playing)
    dc_activity = discord.Activity(name="test", type=discord.ActivityType.playing)
    status = StatusType.online
    dc_status = discord.Status.online
    mocker.patch.object(mock_bot, "_get_discord_presence_from_settings", return_value=[dc_activity, dc_status])

    # Test setting presence with activity and status
    await mock_bot.set_bot_presence(activity=activity, status=status)
    db_mock.update_settings.assert_called_once_with(activity=activity, status=status)
    change_presence_mock.assert_called_once()
    db_mock.update_settings.reset_mock()
    change_presence_mock.reset_mock()

    # Test setting presence with only activity
    await mock_bot.set_bot_presence(activity=activity)
    db_mock.update_settings.assert_called_once_with(activity=activity)
    change_presence_mock.assert_called_once()
    db_mock.update_settings.reset_mock()
    change_presence_mock.reset_mock()

    # Test setting presence with only status
    await mock_bot.set_bot_presence(status=status)
    db_mock.update_settings.assert_called_once_with(status=status)
    change_presence_mock.assert_called_once()
    db_mock.update_settings.reset_mock()
    change_presence_mock.reset_mock()

    # Test clearing presence
    await mock_bot.clear_bot_presence()
    db_mock.update_settings.assert_called_once_with(activity=None, status=None)
    change_presence_mock.assert_called_once()


def test_database_error_handling(mock_bot: Bot, mocker: MockerFixture) -> None:
    """Test graceful exit on database connection errors during startup."""
    # Mock database client that raises DatabaseError
    db_mock = mocker.MagicMock(spec=DBClientBase)
    db_mock.connect.side_effect = DatabaseError("Test error")
    mock_bot.database_client = db_mock

    with pytest.raises(SystemExit):
        mock_bot.run_bot()


@pytest.mark.asyncio(loop_scope="function")
async def test_command_logging(mock_bot: Bot, context: Context, caplog: pytest.LogCaptureFixture) -> None:
    """Test that command execution logs include relevant permission context."""
    caplog.set_level(logging.DEBUG)

    # Setup command with permission check
    context._perm_check_reason = "test_reason"
    await mock_bot.on_before_invoke(context)

    assert any("test_reason" in record.message for record in caplog.records)

    # Run the command without a reason
    del context._perm_check_reason
    await mock_bot.on_before_invoke(context)


def test_run_bot_keyboard_interrupt(mock_bot: Bot) -> None:
    """Test clean exit when a KeyboardInterrupt occurs during bot startup."""
    # Mock start to raise KeyboardInterrupt
    cast(Mock, mock_bot.start).side_effect = KeyboardInterrupt

    with pytest.raises(SystemExit) as excinfo:
        mock_bot.run_bot()

    # noinspection PyUnreachableCode
    assert excinfo.value.code == 0  # Clean exit


def test_run_bot_privileged_intents_error(mock_bot: Bot) -> None:
    """Test exit when Discord privileged intents are missing."""
    # Mock start to raise PrivilegedIntentsRequired
    cast(Mock, mock_bot.start).side_effect = discord.PrivilegedIntentsRequired(None)

    with pytest.raises(SystemExit) as excinfo:
        mock_bot.run_bot()

    # noinspection PyUnreachableCode
    assert excinfo.value.code == 1  # Error exit


def test_run_bot_login_failure(mock_bot: Bot) -> None:
    """Test bot exit on Discord login failure error."""
    # Mock start to raise LoginFailure
    cast(Mock, mock_bot.start).side_effect = discord.errors.LoginFailure

    with pytest.raises(SystemExit) as excinfo:
        mock_bot.run_bot()

    # noinspection PyUnreachableCode
    assert excinfo.value.code == 1  # Error exit


def test_run_bot_unknown_error(mock_bot: Bot) -> None:
    """Test exit handling for unexpected errors during bot startup."""
    # Mock start to raise a generic Exception
    cast(Mock, mock_bot.start).side_effect = Exception("Unknown error")

    with pytest.raises(SystemExit) as excinfo:
        mock_bot.run_bot()

    # noinspection PyUnreachableCode
    assert excinfo.value.code == 1  # Error exit


def test_run_bot_uvloop_available(mock_bot: Bot, mocker: MockerFixture) -> None:
    """Test that uvloop is used for improved performance during startup."""
    # Mock uvloop import to succeed
    mock_uvloop = mocker.MagicMock()
    mock_uvloop.run = asyncio.run

    original_import = __import__

    def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "uvloop":
            return mock_uvloop
        return original_import(name, *args, **kwargs)

    mocker.patch("builtins.__import__", mock_import)

    with pytest.raises(SystemExit) as excinfo:
        mock_bot.run_bot()

    # noinspection PyUnreachableCode
    assert excinfo.value.code == 0  # Clean exit
    mock_bot.start.assert_called_once()


def test_run_bot_uvloop_import_error(mock_bot: Bot, mocker: MockerFixture) -> None:
    """Test fallback to asyncio when uvloop is not available."""
    # Mock uvloop import to fail
    original_import = __import__

    def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "uvloop":
            raise ModuleNotFoundError("Module 'uvloop' not found", name="uvloop")
        return original_import(name, *args, **kwargs)

    mocker.patch("builtins.__import__", mock_import)

    # Mock sys.platform to be non-Windows
    mocker.patch("sys.platform", "linux")

    with pytest.raises(SystemExit) as excinfo:
        mock_bot.run_bot()

    # noinspection PyUnreachableCode
    assert excinfo.value.code == 0  # Clean exit
    mock_bot.start.assert_called_once()


def test_run_bot_with_jishaku(mock_bot: Bot, mocker: MockerFixture) -> None:
    """Test that the jishaku extension is loaded when enabled in configuration."""
    # Mock CONFIG to enable jishaku
    mocker.patch("modmail.core.bot.CONFIG.bot.enable_jishaku", True)

    # Mock load_extension to track calls
    load_extension_mock = mocker.patch.object(mock_bot, "load_extension")

    with pytest.raises(SystemExit) as excinfo:
        mock_bot.run_bot()

    # Verify that jishaku was loaded
    # noinspection PyUnreachableCode
    assert excinfo.value.code == 0  # Clean exit
    load_extension_mock.assert_any_call("jishaku")
    mock_bot.start.assert_called_once()


@pytest.mark.asyncio(loop_scope="function")
async def test_on_event_valid(mock_bot: Bot, mocker: MockerFixture) -> None:
    """Test execution of built-in event handlers."""
    set_bot_presence_mock = mocker.patch.object(mock_bot, "set_bot_presence")
    await mock_bot.on_ready()
    await mock_bot.on_connect()
    set_bot_presence_mock.assert_called_once()


def test_get_discord_presence_from_settings(mock_bot: Bot, mocker: MockerFixture) -> None:
    """Test conversion of internal activity/status models to Discord API objects."""
    settings_mock = mocker.MagicMock(spec=Settings)
    cast(Mock, mock_bot.database_client).settings_model = settings_mock

    # Test case 1: No activity or status
    settings_mock.activity = None
    settings_mock.status = None
    activity, status = mock_bot._get_discord_presence_from_settings()
    assert activity is None
    assert status is None

    # Test case 2: Custom activity
    custom_activity = Activity(type=ActivityType.custom, name="Custom Status")
    settings_mock.activity = custom_activity
    settings_mock.status = StatusType.online
    activity, status = mock_bot._get_discord_presence_from_settings()
    assert isinstance(activity, discord.CustomActivity)
    assert activity.name == "Custom Status"
    assert status == discord.Status.online

    # Test case 3: Playing activity
    playing_activity = Activity(type=ActivityType.playing, name="Minecraft")
    settings_mock.activity = playing_activity
    activity, status = mock_bot._get_discord_presence_from_settings()
    assert isinstance(activity, discord.Activity)
    assert activity.name == "Minecraft"
    assert activity.type == discord.ActivityType.playing

    # Test case 4: Streaming activity with valid URL
    streaming_activity = Activity(
        type=ActivityType.streaming, name="Some Game", url="https://www.twitch.tv/username"
    )
    settings_mock.activity = streaming_activity
    activity, status = mock_bot._get_discord_presence_from_settings()
    assert isinstance(activity, discord.Streaming)
    assert activity.name == "Some Game"
    assert activity.url == "https://www.twitch.tv/username"

    # Test case 5: Streaming activity with missing URL (uses default)
    streaming_activity = Activity(type=ActivityType.streaming, name="Some Game", url=None)
    settings_mock.activity = streaming_activity
    activity, status = mock_bot._get_discord_presence_from_settings()
    assert isinstance(activity, discord.Streaming)
    assert activity.name == "Some Game"
    assert activity.url == "https://www.twitch.tv/live"

    # Test case 6: Streaming activity with invalid URL (uses default)
    streaming_activity = Activity(type=ActivityType.streaming, name="Some Game", url="https://youtube.com/invalid")
    settings_mock.activity = streaming_activity
    activity, status = mock_bot._get_discord_presence_from_settings()
    assert isinstance(activity, discord.Streaming)
    assert activity.name == "Some Game"
    assert activity.url == "https://www.twitch.tv/live"

    # Test case 7: Status only
    settings_mock.activity = None
    settings_mock.status = StatusType.dnd
    activity, status = mock_bot._get_discord_presence_from_settings()
    assert activity is None
    assert status == discord.Status.dnd

    # Test case 8: Other activity types
    for activity_type in [ActivityType.listening, ActivityType.watching, ActivityType.competing]:
        test_activity = Activity(type=activity_type, name="Test Name")
        settings_mock.activity = test_activity
        activity, status = mock_bot._get_discord_presence_from_settings()
        assert isinstance(activity, discord.Activity)
        assert activity.name == "Test Name"
        assert activity.type == discord.ActivityType[activity_type.name]


@pytest.mark.asyncio(loop_scope="function")
async def test_on_command_error(mock_bot: Bot, context: Context, mocker: MockerFixture) -> None:
    """Test error handling in commands, propagating non-ignored errors."""
    # Mock the super().on_command_error method
    super_error_handler = mocker.patch.object(commands.Bot, "on_command_error")

    # Test case 1: CommandNotFound error (should be ignored)
    error = commands.CommandNotFound()
    await mock_bot.on_command_error(context, error)
    super_error_handler.assert_not_called()
    super_error_handler.reset_mock()

    # Test case 2: CheckFailure error (should be ignored)
    error = commands.CheckFailure()
    context._perm_check_reason = "test reason"
    await mock_bot.on_command_error(context, error)
    super_error_handler.assert_not_called()
    super_error_handler.reset_mock()

    # Test case 3: Other errors (should be propagated to super)
    error = commands.MissingRequiredArgument(param=mocker.MagicMock(spec=commands.Parameter))
    await mock_bot.on_command_error(context, error)
    super_error_handler.assert_called_once_with(context, error)
