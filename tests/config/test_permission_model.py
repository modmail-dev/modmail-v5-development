from __future__ import annotations

from typing import Any, cast

import pytest

from modmail.config.models.permission_model import PermissionConfig
from modmail.enum import RequiredAccessLevel


def test_permission_config_defaults() -> None:
    """Test that PermissionConfig initializes with expected default values."""
    config = PermissionConfig()

    assert isinstance(config.default_access_everyone, bool)
    assert isinstance(config.slash_minimum_permission_int, int)
    assert isinstance(config.overrides, dict)


def test_permission_config_custom_values() -> None:
    """Test that PermissionConfig correctly applies custom values during initialization."""
    config = PermissionConfig(
        discord_admin_bypass=False,
        default_access_everyone=False,
        slash_minimum_permission_int=8,
        overrides={"help": RequiredAccessLevel.everyone, "close": RequiredAccessLevel.manager},
    )

    assert config.discord_admin_bypass is False
    assert config.default_access_everyone is False
    assert config.slash_minimum_permission_int == 8
    assert config.overrides == {"help": RequiredAccessLevel.everyone, "close": RequiredAccessLevel.manager}


def test_permission_config_overrides_sanitization() -> None:
    """Test that command names in overrides are properly sanitized."""
    config = PermissionConfig(
        overrides={"HELP Command": RequiredAccessLevel.everyone, " CLOSE thread ": RequiredAccessLevel.manager}
    )

    assert "help command" in config.overrides
    assert "close thread" in config.overrides
    assert config.overrides["help command"] == RequiredAccessLevel.everyone
    assert config.overrides["close thread"] == RequiredAccessLevel.manager


def test_permission_config_overrides_string_access_levels() -> None:
    """Test that string access levels in overrides are correctly converted to enums."""
    config = PermissionConfig(
        overrides=cast(dict[str, Any], {"help": "EVERYONE", "close": "ManaGER", "ban": "admin"})
    )

    assert config.overrides["help"] == RequiredAccessLevel.everyone
    assert config.overrides["close"] == RequiredAccessLevel.manager
    assert config.overrides["ban"] == RequiredAccessLevel.admin


def test_permission_config_invalid_access_level() -> None:
    """Test that providing an invalid access level raises a ValueError."""
    with pytest.raises(ValueError, match=r"Invalid permission access level: invalid_level"):
        PermissionConfig(overrides=cast(dict[str, Any], {"help": "invalid_level"}))


def test_permission_config_none_overrides() -> None:
    """Test that None for overrides is converted to an empty dictionary."""
    config_dict = {"discord_admin_bypass": True, "overrides": None}

    config = PermissionConfig(**cast(dict[str, Any], config_dict))
    assert config.overrides == {}


def test_permission_config_negative_slash_permission() -> None:
    """Test that negative values for slash_minimum_permission_int are rejected."""
    with pytest.raises(ValueError):
        PermissionConfig(slash_minimum_permission_int=-1)
