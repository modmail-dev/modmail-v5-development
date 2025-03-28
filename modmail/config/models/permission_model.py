"""
modmail.config.models.permission_model
======================================
Contains configuration models for the permission system.
Defines the structure and validation for permission-related settings.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from modmail import utils
from modmail.enum import RequiredAccessLevel

__all__ = ["PermissionConfig"]


class PermissionConfig(BaseModel):
    """
    Configuration model for the permission system.

    Attributes:
        discord_admin_bypass (bool): Whether users with Discord administrator permission
                                     should be given Modmail admin access level.
        default_access_everyone (bool): Whether everyone should have access to commands
                                        with "everyone" access level by default.
        slash_minimum_permission_int (int): Minimum Discord permissions to see slash commands.
        overrides (dict[str, RequiredAccessLevel]): Override a command's required access level.
    """

    discord_admin_bypass: bool = True
    default_access_everyone: bool = True
    slash_minimum_permission_int: Annotated[int, Field(ge=0)] = 11264
    overrides: dict[str, RequiredAccessLevel] = Field(default_factory=dict, validate_default=True)

    @field_validator("overrides", mode="before")
    @classmethod
    def sanitize_overrides_values_config(
        cls, v: dict[str, RequiredAccessLevel | str] | None
    ) -> dict[str, RequiredAccessLevel]:
        """
        Sanitizes the overrides command names and parses the access levels.
        """
        if v is None:
            return {}

        new_v: dict[str, RequiredAccessLevel] = {}
        for key, value in v.items():
            key = utils.sanitize_user_command_name(key)
            if isinstance(value, str):
                try:
                    new_v[key] = RequiredAccessLevel[value.casefold()]
                except KeyError as e:
                    raise ValueError(f"Invalid permission access level: {value}") from e
            else:
                new_v[key] = value
        return new_v
