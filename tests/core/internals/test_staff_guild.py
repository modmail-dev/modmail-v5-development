from __future__ import annotations

import logging
from typing import cast
from unittest.mock import Mock

import discord
import pytest
from pytest_mock import MockerFixture

from modmail.backends.common import DBClientBase
from modmail.core import Translator
from modmail.core.bot import Bot
from modmail.core.internals.staff_guild import StaffGuild
from modmail.enum import ProfileType
from modmail.errors import NoStaffGuildError


@pytest.fixture
def mock_bot(mocker: MockerFixture) -> Bot:
    """Create a mock bot instance with basic configuration.

    Returns:
        The mock bot instance.
    """
    bot = mocker.MagicMock(spec=Bot)
    bot.database_client = mocker.MagicMock(spec=DBClientBase)
    bot.database_client.settings_model.main_category_id = 1234567889012345
    bot.database_client.settings_model.log_channel_id = 12345678890123456
    bot.database_client.settings_model.storage_channel_id = 12345678890123457
    bot.translator = mocker.MagicMock(spec=Translator)
    return bot


@pytest.fixture
def mock_guild(mocker: MockerFixture) -> discord.Guild:
    """Create a mock guild with basic configuration.

    Returns:
        The mock guild instance.
    """
    guild = mocker.MagicMock(spec=discord.Guild)
    guild.name = "Test Guild"

    category = mocker.MagicMock(spec=discord.CategoryChannel)
    category.id = 1234567889012345
    category.permissions_for.return_value = discord.Permissions.all()
    guild.categories = [category]
    return guild


@pytest.fixture
def staff_guild(mock_bot: Bot) -> StaffGuild:
    """Create a StaffGuild instance with a mock bot.

    Returns:
        The instance of StaffGuild.
    """
    return StaffGuild(mock_bot)


def test_staff_guild_properties(staff_guild: StaffGuild, mock_bot: Bot, mock_guild: discord.Guild) -> None:
    """Test basic property behavior of StaffGuild."""
    mock_bot.get_guild.return_value = mock_guild

    assert staff_guild.exists is True
    assert staff_guild.guild == mock_guild
    assert str(staff_guild) == "Test Guild"

    repr(staff_guild)

    # Test non-existent guild
    mock_bot.get_guild.return_value = None
    assert staff_guild.exists is False
    assert str(staff_guild) == "<Invalid Guild>"
    with pytest.raises(NoStaffGuildError):
        _ = staff_guild.guild


def test_minimum_permissions(staff_guild: StaffGuild) -> None:
    """Test minimum permission calculations."""
    perms = staff_guild.MIN_PERMISSIONS
    assert isinstance(perms, discord.Permissions)
    assert perms.read_messages
    assert perms.manage_roles
    assert not perms.administrator

    overwrite = staff_guild.MIN_PERMISSIONS_OVERWRITE
    assert isinstance(overwrite, discord.PermissionOverwrite)
    assert overwrite.read_messages is True


def test_channel_permission_validation(
    staff_guild: StaffGuild,
    mock_bot: Bot,
    mock_guild: discord.Guild,
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test channel permission validation logic."""
    # Case 1: Guild doesn't exist
    mock_bot.get_guild.return_value = None
    assert staff_guild.category is None
    assert staff_guild.log_channel is None
    assert staff_guild.storage_channel is None

    # Case 2: Guild exists but channel/category IDs are None
    mock_bot.get_guild.return_value = mock_guild
    mock_bot.database_client.settings_model.main_category_id = None
    mock_bot.database_client.settings_model.log_channel_id = None
    mock_bot.database_client.settings_model.storage_channel_id = None

    assert staff_guild.category is None
    assert staff_guild.log_channel is None
    assert staff_guild.storage_channel is None

    # Case 3: IDs exist but channels/category not found in guild
    mock_bot.database_client.settings_model.main_category_id = 9999  # ID that doesn't exist
    mock_bot.database_client.settings_model.log_channel_id = 9998
    mock_bot.database_client.settings_model.storage_channel_id = 9997

    # Set different IDs on the mock channels
    mock_category = mocker.MagicMock(spec=discord.CategoryChannel)
    mock_category.id = 1111  # Different from settings
    mock_log = mocker.MagicMock(spec=discord.TextChannel)
    mock_log.id = 2222  # Different from settings
    mock_storage = mocker.MagicMock(spec=discord.TextChannel)
    mock_storage.id = 3333  # Different from settings

    mock_guild.categories = [mock_category]
    mock_guild.text_channels = [mock_log, mock_storage]

    assert staff_guild.category is None
    assert staff_guild.log_channel is None
    assert staff_guild.storage_channel is None

    # Case 4: Channels exist but have missing permissions
    # Restore IDs
    mock_bot.database_client.settings_model.main_category_id = 1234567889012345
    mock_bot.database_client.settings_model.log_channel_id = 12345678890123456
    mock_bot.database_client.settings_model.storage_channel_id = 12345678890123457

    incomplete_perms = discord.Permissions(read_messages=True)  # Missing required perms
    mock_category = mocker.MagicMock(spec=discord.CategoryChannel)
    mock_category.permissions_for.return_value = incomplete_perms
    mock_category.guild = mock_guild
    mock_category.id = mock_bot.database_client.settings_model.main_category_id

    # Setup log channel with missing permissions
    mock_log = mocker.MagicMock(spec=discord.TextChannel)
    mock_log.permissions_for.return_value = incomplete_perms
    mock_log.guild = mock_guild
    mock_log.id = mock_bot.database_client.settings_model.log_channel_id

    # Setup storage channel with missing permissions
    mock_storage = mocker.MagicMock(spec=discord.TextChannel)
    mock_storage.permissions_for.return_value = incomplete_perms
    mock_storage.guild = mock_guild
    mock_storage.id = mock_bot.database_client.settings_model.storage_channel_id

    # Add all channels to guild
    mock_guild.categories = [mock_category]
    mock_guild.text_channels = [mock_log, mock_storage]

    with caplog.at_level(logging.CRITICAL):
        # Test category permissions
        assert staff_guild.category is None
        assert "permissions were missing from the main category" in caplog.text

        # Test log channel permissions
        caplog.clear()
        assert staff_guild.log_channel is None
        assert "permissions were missing from the log channel" in caplog.text

        # Test storage channel permissions
        caplog.clear()
        assert staff_guild.storage_channel is None
        assert "permissions were missing from the storage channel" in caplog.text

    # Case 5: All conditions met, properties return successfully
    complete_perms = staff_guild.MIN_PERMISSIONS

    mock_category.permissions_for.return_value = complete_perms
    mock_log.permissions_for.return_value = complete_perms
    mock_storage.permissions_for.return_value = complete_perms

    assert staff_guild.category == mock_category
    assert staff_guild.log_channel == mock_log
    assert staff_guild.storage_channel == mock_storage


@pytest.mark.asyncio
async def test_access_management(
    staff_guild: StaffGuild,
    mock_bot: Bot,
    mock_guild: discord.Guild,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test granting and revoking access with all edge cases."""
    mock_bot.get_guild.return_value = mock_guild

    # Setup mocks
    mock_category = mocker.MagicMock(spec=discord.CategoryChannel)
    mock_storage = mocker.MagicMock(spec=discord.TextChannel)

    # Set up default overwrites
    default_overwrite = discord.PermissionOverwrite(read_messages=True)
    modified_overwrite = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    # Mock CONFIG.bot.bot_id
    mocker.patch("modmail.config.models.BotConfig.bot_id", 999)

    # Mock translator
    mock_bot.translator.translate.return_value = "Translated reason"

    # Test 1: Not configured guild
    mocker.patch.object(staff_guild, "is_configured", return_value=False)

    await staff_guild.grant_access(123, ProfileType.user)
    await staff_guild.revoke_access(123, ProfileType.user)

    # Test 2: Configured guild - setup mocks
    mocker.patch.object(staff_guild, "is_configured", return_value=True)
    monkeypatch.setattr("modmail.core.internals.StaffGuild.category", mock_category)
    monkeypatch.setattr("modmail.core.internals.StaffGuild.storage_channel", mock_storage)

    # Test 3: Bot ID case
    with caplog.at_level(logging.DEBUG):
        await staff_guild.grant_access(999, ProfileType.user)
        assert "Not granting access to the bot itself" in caplog.text

        caplog.clear()
        await staff_guild.revoke_access(999, ProfileType.user)
        assert "Not revoking access from the bot itself" in caplog.text

    # Test 4: User not found case
    mock_guild.fetch_member.side_effect = discord.NotFound(mocker.MagicMock(), "Not found")

    with caplog.at_level(logging.INFO):
        await staff_guild.grant_access(123, ProfileType.user)
        assert "Not granting access to 123, user not in guild" in caplog.text

        caplog.clear()
        await staff_guild.revoke_access(123, ProfileType.user)
        assert "Not revoking access from 123, user not in guild" in caplog.text

    # Test 5: Role not found case
    mock_guild.get_role.return_value = None

    with caplog.at_level(logging.INFO):
        await staff_guild.grant_access(123, ProfileType.role)
        assert "Not granting access to 123, role not in guild" in caplog.text

        caplog.clear()
        await staff_guild.revoke_access(123, ProfileType.role)
        assert "Not revoking access from 123, role not in guild" in caplog.text

    # Test 6: Success case - grant user access
    mock_member = mocker.MagicMock(spec=discord.Member)
    mock_guild.fetch_member.side_effect = None
    mock_guild.fetch_member.return_value = mock_member
    mock_category.overwrites_for.return_value = default_overwrite
    mock_storage.overwrites_for.return_value = default_overwrite

    await staff_guild.grant_access(123, ProfileType.user)

    # Verify permissions were set correctly for both channels
    mock_category.set_permissions.assert_called_once_with(
        mock_member, overwrite=default_overwrite, reason="Translated reason"
    )
    mock_storage.set_permissions.assert_called_once_with(
        mock_member, overwrite=default_overwrite, reason="Translated reason"
    )

    # Reset mocks
    mock_category.set_permissions.reset_mock()
    mock_storage.set_permissions.reset_mock()

    # Test 7: Success case - grant role access
    mock_role = mocker.MagicMock(spec=discord.Role)
    mock_guild.get_role.return_value = mock_role

    await staff_guild.grant_access(123, ProfileType.role)

    mock_category.set_permissions.assert_called_once_with(
        mock_role, overwrite=default_overwrite, reason="Translated reason"
    )
    mock_storage.set_permissions.assert_called_once_with(
        mock_role, overwrite=default_overwrite, reason="Translated reason"
    )

    # Test 8: Revoke access - default overwrites
    mock_category.set_permissions.reset_mock()
    mock_storage.set_permissions.reset_mock()
    mock_category.overwrites_for.return_value = default_overwrite
    mock_storage.overwrites_for.return_value = default_overwrite

    await staff_guild.revoke_access(123, ProfileType.user)

    # Verify permissions were reset
    mock_category.set_permissions.assert_called_once_with(mock_member, overwrite=None, reason="Translated reason")
    mock_storage.set_permissions.assert_called_once_with(mock_member, overwrite=None, reason="Translated reason")

    # Test 9: Revoke access - modified overwrites
    mock_category.set_permissions.reset_mock()
    mock_storage.set_permissions.reset_mock()
    mock_category.overwrites_for.return_value = modified_overwrite
    mock_storage.overwrites_for.return_value = modified_overwrite

    with caplog.at_level(logging.INFO):
        caplog.clear()
        await staff_guild.revoke_access(123, ProfileType.user)
        assert "Not revoking access to" in caplog.text
        assert "overwrites were modified" in caplog.text

    # Verify no permissions were changed
    mock_category.set_permissions.assert_not_called()
    mock_storage.set_permissions.assert_not_called()


@pytest.mark.asyncio
async def test_setup(
    staff_guild: StaffGuild,
    mock_bot: Bot,
    mocker: MockerFixture,
) -> None:
    """Test staff guild setup process."""
    mock_category = mocker.MagicMock(spec=discord.CategoryChannel)
    mock_log = mocker.MagicMock(spec=discord.TextChannel)
    mock_storage = mocker.MagicMock(spec=discord.TextChannel)

    await staff_guild.setup(mock_category, mock_log, mock_storage)

    # Verify database was updated
    mock_bot.database_client.update_settings.assert_called_once_with(
        main_category_id=mock_category.id,
        log_channel_id=mock_log.id,
        storage_channel_id=mock_storage.id,
    )


@pytest.mark.asyncio
async def test_error_handling(
    staff_guild: StaffGuild,
    mock_bot: Bot,
    mock_guild: discord.Guild,
    mocker: MockerFixture,
) -> None:
    """Test error handling scenarios."""
    mock_bot.get_guild.return_value = mock_guild

    # Test handling non-existent member
    mock_guild.fetch_member.side_effect = discord.NotFound(mocker.MagicMock(), "Not found")

    # Should not raise an exception
    await staff_guild.grant_access(999, ProfileType.user)
    await staff_guild.revoke_access(999, ProfileType.user)

    # Test handling non-existent role
    mock_guild.get_role.return_value = None

    # Should not raise an exception
    await staff_guild.grant_access(999, ProfileType.role)
    await staff_guild.revoke_access(999, ProfileType.role)


def test_is_configured(
    staff_guild: StaffGuild, mock_bot: Bot, mock_guild: discord.Guild, mocker: MockerFixture
) -> None:
    """Test configuration state detection."""
    mock_bot.get_guild.return_value = mock_guild

    # Test with missing category
    cast(Mock, mock_guild).categories = []
    assert staff_guild.is_configured() is False

    # Test with valid category
    category = mocker.MagicMock(spec=discord.CategoryChannel)
    category.guild = mock_guild
    cast(Mock, mock_guild).categories = [category]
    mock_bot.database_client.settings_model.main_category_id = category.id

    # Ensure proper permissions
    category.permissions_for = lambda _: staff_guild.MIN_PERMISSIONS
    assert staff_guild.is_configured() is True
