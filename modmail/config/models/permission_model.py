"""
modmail.config.models.permission_model
======================================
Contains configuration models for the permission system.
Defines the structure and validation for permission-related settings.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from modmail.enum import RequiredAccessLevel

__all__ = ["PermissionConfig"]


# noinspection PyNestedDecorators
class PermissionConfig(BaseModel):
    """
    Configuration model for the permission system.

    Attributes:
        discord_admin_bypass (bool): Whether users with Discord administrator permission should be given Modmail admin access level.
        overrides (dict[str, RequiredAccessLevel]): Override a command's required access level.
    """

    discord_admin_bypass: bool = True
    overrides: dict[str, RequiredAccessLevel] = Field(default_factory=dict, validate_default=True)

    @field_validator("overrides", mode="before")
    @classmethod
    def set_default_overrides_config(
        cls, v: dict[str, RequiredAccessLevel] | None
    ) -> dict[str, RequiredAccessLevel]:
        """
        Sets the default overrides if not provided.
        """
        if v is None:
            return {}
        return v

    @field_validator("overrides", mode="before")
    @classmethod
    def sanitize_overrides_values_config(
        cls, v: dict[str, RequiredAccessLevel | str]
    ) -> dict[str, RequiredAccessLevel]:
        """
        Sanitizes the overrides command names and parses the access levels.
        """
        new_v: dict[str, RequiredAccessLevel] = {}
        for key, value in v.items():
            # Replace spaces and dashes with underscores and convert to lowercase
            key = key.casefold().strip().replace(" ", "_").replace("-", "_")
            if isinstance(value, str):
                try:
                    # noinspection PyTypeChecker
                    new_v[key] = RequiredAccessLevel[value.casefold()]
                except KeyError:
                    raise ValueError(f"Invalid permission access level: {value}")
            else:
                new_v[key] = value
        return new_v
