"""Permission configuration models for Modmail.

This module contains configuration models for the permission system.
It defines the structure and validation for permission-related settings.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from modmail import utils
from modmail.enum import RequiredAccessLevel

__all__ = ["PermissionConfig"]


class PermissionConfig(BaseModel):
    """Configuration model for the permission system.

    Attributes:
        discord_admin_bypass: Whether users with Discord administrator permission
            should be given Modmail admin access level.
        default_access_everyone: Whether everyone should have access to commands
            with "everyone" access level by default.
        slash_minimum_permission_int: Minimum Discord permissions integer value
            required to see slash commands.
        overrides: Mapping of command names to their required access levels,
            allowing customization of command permissions.
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
        """Sanitizes command names and parses access levels in the overrides mapping.

        Args:
            v: Dictionary mapping command names to their required access levels,
               which can be either RequiredAccessLevel enum values or strings.

        Returns:
            A dictionary mapping sanitized command names to RequiredAccessLevel enum values.

        Raises:
            ValueError: If an invalid permission access level string is provided.
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
