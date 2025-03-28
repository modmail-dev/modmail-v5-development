from __future__ import annotations

from discord import app_commands

from modmail.enum import AccessLevel, ActivityType, ProfileKey, ProfileType, RequiredAccessLevel, StatusType
from modmail.errors import DatabaseConnectionError, DatabaseError, ModmailError


class TestErrors:
    def test_error_instantiation(self) -> None:
        """Test that all custom exception classes correctly store and return error messages."""
        error_msg = "Test error message"

        # Test case 1: Base ModmailError
        modmail_error = ModmailError(error_msg)
        assert str(modmail_error) == error_msg

        # Test case 2: DatabaseError
        db_error = DatabaseError(error_msg)
        assert str(db_error) == error_msg

        # Test case 3: DatabaseConnectionError
        db_conn_error = DatabaseConnectionError(error_msg)
        assert str(db_conn_error) == error_msg


class TestEnums:
    def test_profile_key(self) -> None:
        """Test that ProfileKey namedtuple correctly stores and retrieves profile identifiers."""
        profile_id = 123
        profile_type = ProfileType.user
        key = ProfileKey(profile_id=profile_id, profile_type=profile_type)
        assert key.profile_id == profile_id
        assert key.profile_type == profile_type


class TestEnumLocalization:
    def test_enum_has_locale_str(self) -> None:
        """Test that all enum values properly implement the __locale_str__ method for localization."""
        # Test case 1: AccessLevel enum values
        for level in AccessLevel:
            assert isinstance(level.__locale_str__(), app_commands.locale_str)

        # Test case 2: RequiredAccessLevel enum values
        for level in RequiredAccessLevel:
            assert isinstance(level.__locale_str__(), app_commands.locale_str)

        # Test case 3: ActivityType enum values
        for activity in ActivityType:
            assert isinstance(activity.__locale_str__(), app_commands.locale_str)

        # Test case 4: StatusType enum values
        for status in StatusType:
            str(status)  # Ensure __str__ works
            assert isinstance(status.__locale_str__(), app_commands.locale_str)
