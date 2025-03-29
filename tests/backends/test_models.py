from __future__ import annotations

import pytest
from discord import app_commands
from pytest_mock import MockFixture

from modmail.backends.common import Activity, Profile, Settings
from modmail.enum import AccessLevel, ActivityType, PermissionOverrideValue, ProfileType, StatusType


class TestActivityModel:
    """Tests for the Activity model."""

    def test_activity_instantiation(self) -> None:
        """Test that Activity model correctly handles different initialization scenarios."""
        # Test case 1: Basic instantiation
        activity = Activity(type=ActivityType.playing, name="Minecraft")
        assert activity.type == ActivityType.playing
        assert activity.name == "Minecraft"
        assert activity.url is None

        # Test case 2: With URL for streaming
        activity = Activity(type=ActivityType.streaming, name="Live coding", url="https://twitch.tv/example")
        assert activity.type == ActivityType.streaming
        assert activity.name == "Live coding"
        assert activity.url == "https://twitch.tv/example"

        # Test case 3: URL is optional even for streaming
        activity = Activity(type=ActivityType.streaming, name="Live coding")
        assert activity.url is None

    def test_activity_str_representation(self) -> None:
        """Test that the string representation of activities is correct for all types."""
        test_cases = [
            (ActivityType.playing, "Test Game", None, "Playing Test Game"),
            (
                ActivityType.streaming,
                "Live Stream",
                "https://twitch.tv/test",
                "Streaming Live Stream (https://twitch.tv/test)",
            ),
            (ActivityType.streaming, "Live Stream", None, "Streaming Live Stream (No URL)"),
            (ActivityType.listening, "Music", None, "Listening to Music"),
            (ActivityType.watching, "Movies", None, "Watching Movies"),
            (ActivityType.custom, "Happy", None, "Happy (custom)"),
            (ActivityType.competing, "Tournament", None, "Competing in Tournament"),
        ]

        for activity_type, name, url, expected_str in test_cases:
            activity = Activity(type=activity_type, name=name, url=url)
            assert str(activity) == expected_str

    def test_activity_locale_str(self, mocker: MockFixture) -> None:
        """Test that the locale_str method returns a properly formatted app_commands.locale_str."""
        # Mock the _ function from modmail.core
        mock_ = mocker.patch("modmail.core._", autospec=True)
        mock_.return_value = app_commands.locale_str("test_locale_key")

        activity = Activity(type=ActivityType.playing, name="Test Game")
        locale_str = activity.__locale_str__()

        # Verify the result is a locale_str
        assert isinstance(locale_str, app_commands.locale_str)
        assert locale_str.message == "test_locale_key"

        # Verify _ was called with correct parameters
        mock_.assert_called_once_with(
            "ftl-model-activity-text",
            activity_type=ActivityType.playing,
            activity_name="Test Game",
            activity_url=None,
        )

    def test_activity_immutability(self) -> None:
        """Test that the Activity model is immutable as specified by ConfigDict(frozen=True)."""
        activity = Activity(type=ActivityType.playing, name="Minecraft")

        with pytest.raises(Exception, match=r"name"):
            activity.name = "Changed Game"  # This should raise an exception due to frozen=True


class TestSettingsModel:
    """Tests for the Settings model."""

    def test_settings_instantiation(self) -> None:
        """Test that Settings model correctly handles different initialization scenarios."""
        # Test case 1: Minimal instantiation with only required fields
        settings = Settings(bot_id=12345678901234567)
        assert settings.bot_id == 12345678901234567
        assert settings.last_ran_version is None
        assert settings.status is None
        assert settings.activity is None

        # Test case 2: Full instantiation
        activity = Activity(type=ActivityType.playing, name="Test")
        settings = Settings(
            bot_id=12345678901234567,
            last_ran_version="1.0.0",
            last_ran_locale="en-US",
            last_slash_synced_version="1.0.0",
            last_slash_minimum_permission_int=8,
            main_category_id=123456789012345678,
            fallback_category_id=123456789012345679,
            status=StatusType.online,
            activity=activity,
        )

        assert settings.bot_id == 12345678901234567
        assert settings.last_ran_version == "1.0.0"
        assert settings.last_ran_locale == "en-US"
        assert settings.last_slash_synced_version == "1.0.0"
        assert settings.last_slash_minimum_permission_int == 8
        assert settings.main_category_id == 123456789012345678
        assert settings.fallback_category_id == 123456789012345679
        assert settings.status == StatusType.online
        assert settings.activity is not None
        assert settings.activity == activity
        assert settings.activity.name == "Test"

    def test_settings_immutability(self) -> None:
        """Test that the Settings model is immutable as specified by ConfigDict(frozen=True)."""
        settings = Settings(bot_id=12345678901234567)

        with pytest.raises(Exception, match=r"bot_id"):
            settings.bot_id = 12345678901234568  # This should raise an exception due to frozen=True

    def test_settings_with_activity_nesting(self) -> None:
        """Test that Settings correctly handles nested Activity objects."""
        # Test with activity dict conversion
        settings = Settings(
            bot_id=12345678901234567,
            activity={"type": ActivityType.playing, "name": "Converted Game"},  # pyright: ignore [reportArgumentType]
        )

        assert settings.activity is not None
        assert isinstance(settings.activity, Activity)
        assert settings.activity.type == ActivityType.playing
        assert settings.activity.name == "Converted Game"

        # Test with Activity object
        activity = Activity(type=ActivityType.watching, name="A Movie")
        settings = Settings(bot_id=12345678901234567, activity=activity)

        assert settings.activity is not None
        assert settings.activity.type == ActivityType.watching
        assert settings.activity.name == "A Movie"


class TestProfileModel:
    """Tests for the Profile model."""

    def test_profile_instantiation(self) -> None:
        """Test that Profile model correctly handles different initialization scenarios."""
        # Test case 1: Basic instantiation with required fields
        profile = Profile(bot_id=12345678901234567, profile_id=12345678901234568, profile_type=ProfileType.user)
        assert profile.bot_id == 12345678901234567
        assert profile.profile_id == 12345678901234568
        assert profile.profile_type == ProfileType.user
        assert profile.access_level is None
        assert profile.permission_overrides == {}
        assert profile.tag is None
        assert profile.colour is None

        # Test case 2: Full instantiation
        profile = Profile(
            bot_id=12345678901234567,
            profile_id=12345678901234568,
            profile_type=ProfileType.user,
            access_level=AccessLevel.everyone,
            permission_overrides={"help": PermissionOverrideValue.allow, "ban": PermissionOverrideValue.deny},
            tag="Support Staff",
            colour=0xFF5500,
        )

        assert profile.bot_id == 12345678901234567
        assert profile.profile_id == 12345678901234568
        assert profile.profile_type == ProfileType.user
        assert profile.access_level == AccessLevel.everyone
        assert profile.permission_overrides == {
            "help": PermissionOverrideValue.allow,
            "ban": PermissionOverrideValue.deny,
        }
        assert profile.tag == "Support Staff"
        assert profile.colour == 0xFF5500

    def test_profile_permission_overrides(self) -> None:
        """Test that permission_overrides dictionary handles different scenarios correctly."""
        # Empty overrides
        profile = Profile(bot_id=12345678901234567, profile_id=12345678901234568, profile_type=ProfileType.user)
        assert profile.permission_overrides == {}

        # Multiple overrides
        overrides = {
            "command1": PermissionOverrideValue.allow,
            "command2": PermissionOverrideValue.deny,
            "command3": PermissionOverrideValue.allow,
        }
        profile = Profile(
            bot_id=123, profile_id=456, profile_type=ProfileType.user, permission_overrides=overrides
        )
        assert profile.permission_overrides == overrides
        assert len(profile.permission_overrides) == 3

    def test_profile_with_role_type(self) -> None:
        """Test the Profile model with role type."""
        profile = Profile(
            bot_id=12345678901234567,
            profile_id=12345678901234568,
            profile_type=ProfileType.role,
            access_level=AccessLevel.admin,
        )

        assert profile.profile_type == ProfileType.role
        assert profile.access_level == AccessLevel.admin

    def test_profile_immutability(self) -> None:
        """Test that the Profile model is immutable as specified by ConfigDict(frozen=True)."""
        profile = Profile(bot_id=12345678901234567, profile_id=12345678901234568, profile_type=ProfileType.user)

        with pytest.raises(Exception, match=r"tag"):
            profile.tag = "New Tag"  # This should raise an exception due to frozen=True
