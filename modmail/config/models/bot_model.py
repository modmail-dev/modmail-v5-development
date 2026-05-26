"""Bot configuration model."""

from __future__ import annotations

import logging
from base64 import b64decode
from typing import Annotated

from pydantic import BaseModel, Field, SecretStr, ValidationInfo, field_validator

__all__ = ["BotConfig"]

logger = logging.getLogger(__name__)

IDType = Annotated[int, Field(gt=100000000000000, lt=99999999999999999999)]  # 15-20 digit integer


class BotConfig(
    BaseModel,
    frozen=True,
    str_strip_whitespace=True,
    coerce_numbers_to_str=True,
    use_attribute_docstrings=True,
):
    """Configuration model for the bot settings."""

    token: SecretStr
    """The bot token used for authentication."""
    staff_server_id: IDType
    """The Discord ID of the staff server."""
    prefix: str | None = "?"  # when prefix is None, the bot will not use a prefix
    """The command prefix for the bot. If None, prefix commands are disabled."""
    respond_bot_mention: bool = True
    """Whether the bot should respond to mentions."""
    owner_ids: set[IDType] = set()
    """A set of user IDs that have owner-level permissions."""
    use_slash_commands: bool = True
    """Whether to use Discord slash commands."""
    force_sync_commands: bool = False
    """Whether to force sync commands with Discord on startup."""
    enable_jishaku: bool = False
    """Whether to enable the jishaku debugging extension."""
    bypass_public_bot_check: bool = False
    """Whether to bypass the public bot check (not recommended)."""
    hide_owner_commands: bool = True
    """Hide owner-only commands from non-owner users in the `/help` menu."""
    hide_inaccessible: bool = True
    """Hide commands the invoking user cannot run in the `/help` menu."""

    @field_validator("token")
    @classmethod
    def check_token_format(cls, v: SecretStr) -> SecretStr:
        """Validates that the bot token has the correct format.

        Args:
            v: The token as a SecretStr to validate.

        Returns:
            The validated token.

        Raises:
            ValueError: If the token format is invalid.
        """
        token = v.get_secret_value()
        if token.count(".") != 2:  # noqa: PLR2004
            raise ValueError("Invalid bot token.")
        try:
            bot_id = int(b64decode(token.split(".")[0] + "=="))
        except Exception as e:
            logger.debug("Invalid bot token: %s", e, exc_info=True)
            raise ValueError("Invalid bot token.") from e
        if len(str(bot_id)) < 15 or len(str(bot_id)) > 20:  # noqa: PLR2004
            raise ValueError("Invalid bot token.")
        return v

    @field_validator("prefix")
    @classmethod
    def check_empty_prefix(cls, v: str | None) -> str | None:
        """Converts empty prefix strings to None to disable prefix commands.

        Args:
            v: The prefix string or None.

        Returns:
            None if empty string, otherwise the original prefix.
        """
        if not v:
            return None  # return None when v is an empty string
        return v

    @field_validator("use_slash_commands")
    @classmethod
    def check_any_command_enabled(cls, v: bool, info: ValidationInfo) -> bool:
        """Ensures at least one command type (slash or prefix) is enabled.

        Args:
            v: Whether slash commands are enabled.
            info: Validation context containing other field values.

        Returns:
            The original slash commands setting.

        Raises:
            ValueError: If both slash commands and prefix commands are disabled.
        """
        if not v and not info.data["prefix"]:
            raise ValueError("Slash commands and prefixed commands cannot be both disabled.")
        return v

    @field_validator("enable_jishaku")
    @classmethod
    def check_jishaku_installed(cls, v: bool) -> bool:
        """Verifies jishaku is installed when enabled.

        Args:
            v: Whether jishaku is enabled in config.

        Returns:
            False if jishaku is enabled but not installed, otherwise the original setting.
        """
        if v:
            try:
                __import__("jishaku")
            except ImportError:
                logger.error("Jishaku is not installed, but is enabled in configs.")
                return False
        return v

    def is_using_prefix(self) -> bool:
        """Determines if the bot is using prefix commands.

        Returns:
            True if the bot is using a prefix, False otherwise.
        """
        return self.prefix is not None

    @property
    def bot_id(self) -> int:
        """Extracts the bot's ID from the token.

        Returns:
            The Discord bot ID as an integer.
        """
        return int(b64decode(self.token.get_secret_value().split(".")[0] + "=="))
