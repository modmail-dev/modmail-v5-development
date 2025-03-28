from __future__ import annotations

from typing import Any, cast

import pytest
from discord.ext import commands
from pytest_mock import MockerFixture

from modmail.utils import (
    colour_hex_to_int,
    get_command_name,
    int_to_colour_hex,
    sanitize_user_command_name,
    strtobool,
)


class TestStrtobool:
    @pytest.mark.parametrize(
        "input_val,expected",
        [
            ("y", 1),
            ("yes", 1),
            ("true", 1),
            ("1", 1),
            ("Y", 1),
            ("n", 0),
            ("no", 0),
            ("f", 0),
            ("off", 0),
            ("0", 0),
            ("False", 0),
        ],
    )
    def test_valid_values(self, input_val: str, expected: int) -> None:
        """Test that strtobool correctly converts various string representations of boolean values."""
        assert strtobool(input_val) == expected

    @pytest.mark.parametrize("invalid_val", ["maybe", "2", "yep", "nope", ""])
    def test_invalid_values(self, invalid_val: str) -> None:
        """Test that strtobool raises ValueError for non-boolean string values."""
        with pytest.raises(ValueError, match=f"invalid truth value {invalid_val!r}"):
            strtobool(invalid_val)


class TestColorConversion:
    @pytest.mark.parametrize(
        "input_int,expected_hex",
        [
            (0x000000, "#000000"),
            (0xFF0000, "#FF0000"),  # Red
            (0x0000FF, "#0000FF"),  # Blue
            (0xFFFFFF, "#FFFFFF"),  # White
        ],
    )
    def test_int_to_colour_hex(self, input_int: int, expected_hex: str) -> None:
        """Test that integer color values correctly convert to hexadecimal color strings."""
        assert int_to_colour_hex(input_int) == expected_hex

    @pytest.mark.parametrize(
        "input_hex,expected_int",
        [
            ("#000000", 0x000000),
            ("#FF0000", 0xFF0000),  # Red
            ("#0000FF", 0x0000FF),  # Blue
            ("#FFFFFF", 0xFFFFFF),  # White
        ],
    )
    def test_colour_hex_to_int(self, input_hex: str, expected_int: int) -> None:
        """Test that hexadecimal color strings correctly convert to integer color values."""
        assert colour_hex_to_int(input_hex) == expected_int


class TestSanitizeUserCommandName:
    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("command", "command"),
            ("command_name", "command name"),
            ("  command  ", "command"),
            ("command+", "command+"),
            ("command*", "command+"),
            ("command_name+", "command name+"),
            (" command_name+ ++ + ", "command name+"),
        ],
    )
    def test_sanitize_user_command_name(self, input_name: str, expected: str) -> None:
        """Test that command names are properly sanitized for user display and permission handling."""
        assert sanitize_user_command_name(input_name) == expected


class TestGetCommandName:
    def test_command_with_command_suffix(self, mocker: MockerFixture) -> None:
        """Test retrieval of command name when function name has a _command suffix."""
        mock_command = mocker.MagicMock(spec=commands.Command)
        mock_command.callback.__name__ = "test_command"
        mock_command.qualified_name = "test"

        result = get_command_name(cast(commands.Command[Any, Any, Any], mock_command))
        assert result == "test"

    def test_command_with_underscore_in_name(self, mocker: MockerFixture) -> None:
        """Test command name resolution when function has underscores but qualified name has spaces."""
        mock_command = mocker.MagicMock(spec=commands.Command)
        mock_command.callback.__name__ = "test_something_command"
        mock_command.qualified_name = "test something"

        result = get_command_name(cast(commands.Command[Any, Any, Any], mock_command))
        assert result == "test something"

    def test_command_with_different_function_name(self, mocker: MockerFixture) -> None:
        """Test that function name parts are accurately extracted when qualified name differs."""
        mock_command = mocker.MagicMock(spec=commands.Command)
        mock_command.callback.__name__ = "test_something_command"
        mock_command.qualified_name = "test"

        result = get_command_name(cast(commands.Command[Any, Any, Any], mock_command))
        assert result == "test something"

    def test_command_without_command_suffix(self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging behavior when command function doesn't follow naming convention."""
        caplog.set_level("DEBUG")
        mock_command = mocker.MagicMock(spec=commands.Command)
        mock_command.callback.__name__ = "test_function"
        mock_command.qualified_name = "test function"

        result = get_command_name(cast(commands.Command[Any, Any, Any], mock_command))
        assert result == "test function"
        assert "does not end with _command" in caplog.text
