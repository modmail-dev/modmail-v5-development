"""
modmail.config.models.bot_model
===============================
This module defines the Pydantic model for the bot configuration settings.
It includes validation logic to ensure the configuration is correct and
provides utility methods for handling bot-specific settings.
"""

from __future__ import annotations

import logging
from base64 import b64decode
from typing import Annotated

from pydantic import BaseModel, Field, SecretStr, ValidationInfo, field_validator

__all__ = [
    "BotConfig",
]

logger = logging.getLogger(__name__)

IDType = Annotated[int, Field(gt=100000000000000, lt=99999999999999999999)]  # 15-20 digit integer


class BotConfig(BaseModel):
    """
    Configuration model for the bot settings.

    Attributes:
        token (str): The bot token.
        staff_server_id (IDType): The ID of the staff server.
        prefix (str | None): The command prefix for the bot.
        respond_bot_mention (bool): Whether the bot should respond to mentions.
        owner_ids (set[IDType]): A set of owner IDs.
        use_slash_commands (bool): Whether to use slash commands.
        force_sync_commands (bool): Whether to force sync commands.
        enable_jishaku (bool): Whether to enable jishaku. Need jishaku installed.
        bypass_public_bot_check (bool): Whether to bypass the public bot check (not recommended).
    """

    token: SecretStr
    staff_server_id: IDType
    prefix: str | None = "?"  # when prefix is None, the bot will not use a prefix
    respond_bot_mention: bool = True
    owner_ids: set[IDType] = set()
    use_slash_commands: bool = True
    force_sync_commands: bool = Field(False, validate_default=True)
    enable_jishaku: bool = False
    bypass_public_bot_check: bool = False

    @field_validator("token")
    @classmethod
    def check_token_format(cls, v: SecretStr) -> SecretStr:
        """
        Checks if the bot token is valid (very basic check).
        """
        token = v.get_secret_value()
        if token.count(".") != 2:
            raise ValueError("Invalid bot token.")
        try:
            bot_id = int(b64decode(token.split(".")[0] + "=="))
        except Exception as e:
            logger.debug(f"Invalid bot token: {e}", exc_info=True)
            raise ValueError("Invalid bot token.")
        if len(str(bot_id)) < 15 or len(str(bot_id)) > 20:
            raise ValueError("Invalid bot token.")
        return v

    @field_validator("prefix")
    @classmethod
    def check_empty_prefix(cls, v: str | None) -> str | None:
        """
        Checks if the prefix is an empty string, and returns None and disable the prefix.
        """
        if not v:
            return None  # return None when v is an empty string
        return v

    @field_validator("use_slash_commands")
    @classmethod
    def check_any_command_enabled(cls, v: bool, info: ValidationInfo) -> bool:
        """
        Checks if either slash commands or prefix command is enabled.
        """
        if not v and not info.data["prefix"]:
            raise ValueError("Slash commands and prefixed commands cannot be both disabled.")
        return v

    @field_validator("owner_ids", mode="before")
    @classmethod
    def handle_empty_owner_ids(cls, v: set[IDType] | None) -> set[IDType]:
        """
        Handles the case where owner_ids is null and sets it to None.
        """
        if not v:
            return set()
        return v

    @field_validator("enable_jishaku")
    @classmethod
    def check_jishaku_installed(cls, v: bool) -> bool:
        """
        Checks if jishaku is installed.
        """
        if v:
            try:
                import jishaku  # type: ignore[import]
            except ImportError:
                logger.error("Jishaku is not installed, but is enabled in configs.")
                return False
        return v

    def is_using_prefix(self):
        """
        Checks if the bot is using a prefix.

        :return: True if the bot is using a prefix, False otherwise.
        """
        return self.prefix is not None

    @property
    def bot_id(self) -> int:
        """
        Gets the bot's ID from the bot token.

        :return: The bot's ID.
        """
        return int(b64decode(self.token.get_secret_value().split(".")[0] + "=="))
