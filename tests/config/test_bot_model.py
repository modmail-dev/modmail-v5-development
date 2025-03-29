from __future__ import annotations

import base64
from typing import Any, cast

import pytest
from pydantic import SecretStr, ValidationError
from pytest_mock import MockFixture

from modmail.config.models.bot_model import BotConfig

VALID_ID = 123456789012345
_encoded_id = base64.b64encode(str(VALID_ID).encode()).decode().rstrip("=")
VALID_TOKEN = cast(SecretStr, f"{_encoded_id}.xyz123.abc")


class TestBotConfig:
    def test_token_validation_success(self) -> None:
        """Test that a properly formatted token is accepted."""
        # Should not raise an exception
        config = BotConfig(token=VALID_TOKEN, staff_server_id=VALID_ID)
        assert config.token.get_secret_value() == VALID_TOKEN

    def test_token_validation_failure_invalid_format(self) -> None:
        """Test that an improperly formatted token is rejected."""
        with pytest.raises(ValidationError, match=r"Invalid bot token"):
            BotConfig(token=cast(SecretStr, "invalid-token"), staff_server_id=VALID_ID)

    def test_token_validation_failure_invalid_bot_token(self) -> None:
        """Test that an invalid token is rejected."""
        invalid_bot_id = 12345678901234  # 14 digits
        encoded_id = base64.b64encode(str(invalid_bot_id).encode()).decode().rstrip("=")
        invalid_token = f"{encoded_id}.xyz123.abc"

        # Bad ID length
        with pytest.raises(ValidationError, match=r"Invalid bot token"):
            BotConfig(token=cast(SecretStr, invalid_token), staff_server_id=VALID_ID)

        # Bad ID format
        with pytest.raises(ValidationError, match=r"Invalid bot token"):
            BotConfig(token=cast(SecretStr, "abc.def.ghi"), staff_server_id=VALID_ID)

    def test_empty_prefix_becomes_none(self) -> None:
        """Test that an empty prefix string becomes None."""
        config = BotConfig(token=VALID_TOKEN, staff_server_id=VALID_ID, prefix="")
        assert config.prefix is None

    def test_command_modes_validation(self) -> None:
        """Test that at least one command mode must be enabled."""
        # Valid: prefix enabled but slash commands disabled
        config = BotConfig(token=VALID_TOKEN, staff_server_id=VALID_ID, prefix="!", use_slash_commands=False)
        assert config.use_slash_commands is False
        assert config.prefix == "!"

        # Valid: slash commands enabled but prefix disabled (None)
        config = BotConfig(token=VALID_TOKEN, staff_server_id=VALID_ID, prefix=None, use_slash_commands=True)
        assert config.use_slash_commands is True
        assert config.prefix is None

        # Invalid: both disabled
        with pytest.raises(ValidationError, match="cannot be both disabled"):
            BotConfig(token=VALID_TOKEN, staff_server_id=VALID_ID, prefix=None, use_slash_commands=False)

    def test_is_using_prefix(self) -> None:
        """Test the is_using_prefix method."""
        config_with_prefix = BotConfig(token=VALID_TOKEN, staff_server_id=VALID_ID, prefix="!")
        assert config_with_prefix.is_using_prefix() is True

        config_without_prefix = BotConfig(token=VALID_TOKEN, staff_server_id=VALID_ID, prefix=None)
        assert config_without_prefix.is_using_prefix() is False

    def test_bot_id_property(self) -> None:
        """Test that bot_id property correctly extracts the ID from token."""
        # Create a token with known ID
        bot_id = 123456789012345678
        encoded_id = base64.b64encode(str(bot_id).encode()).decode().rstrip("=")
        token = f"{encoded_id}.xyz123.abc"

        config = BotConfig(token=cast(SecretStr, token), staff_server_id=VALID_ID)
        assert config.bot_id == bot_id

    def test_owner_ids_empty_becomes_empty_set(self) -> None:
        """Test that None/empty owner_ids becomes an empty set."""
        config = BotConfig(token=VALID_TOKEN, staff_server_id=VALID_ID, owner_ids=cast(set[int], None))
        assert isinstance(config.owner_ids, set)

        config = BotConfig(token=VALID_TOKEN, staff_server_id=VALID_ID, owner_ids=cast(set[int], []))
        assert isinstance(config.owner_ids, set)

    def test_jishaku_check_fail(self, mocker: MockFixture) -> None:
        """Test that jishaku is checked when enabled."""
        # Mock import jishaku to fail
        original_import = __import__

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "jishaku":
                raise ImportError("No module named 'jishaku'")
            return original_import(name, *args, **kwargs)

        mocker.patch("builtins.__import__", mock_import)

        config = BotConfig(token=VALID_TOKEN, staff_server_id=VALID_ID, enable_jishaku=True)

        # Should be automatically set to False when import fails
        assert config.enable_jishaku is False

    def test_jishaku_check_pass(self, mocker: MockFixture) -> None:
        """Test that jishaku is checked when enabled."""
        # Mock import jishaku to fail
        original_import = __import__

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "jishaku":
                return None
            return original_import(name, *args, **kwargs)

        mocker.patch("builtins.__import__", mock_import)

        config = BotConfig(token=VALID_TOKEN, staff_server_id=VALID_ID, enable_jishaku=True)

        assert config.enable_jishaku is True
